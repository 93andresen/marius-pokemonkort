#!/usr/bin/env python3
"""FINN.no search discovery — structured extraction, NO Markdown.

We fetch FINN search-result pages and decode the **embedded JSON** they
server-render (``<script type="application/json" data-react-query-state>``,
base64-encoded). That block contains, losslessly:

  * ``docs``     — the ad documents for the page (id / heading / price /
                   location / coordinates / labels / images / …)
  * ``metadata`` — pagination + counts (``paging.current/last``,
                   ``result_size.match_count``, ``num_results`` …)
  * ``filters``  — the **complete machine-readable filter/parameter map**

The raw HTML is stored as an immutable source; parsed docs JSONL are written
downstream (so a parser fix can always be re-run without re-fetching — spec
§0.2/§0.3). Nothing is ever deleted (spec §0.1).

Examples
--------
  # One page of a single query, newest first (default):
  uv run finn/finn_search.py -q "pokemon kort"

  # All pages, two sorts, into a specific run dir:
  uv run finn/finn_search.py -q "pokemon kort" --all-pages --sort PUBLISHED_DESC,RELEVANCE

  # The complete parameter map (sub_category / product_category / …):
  uv run finn/finn_search.py -q "pokemon kort" \\
      --param sub_category=1.86.285 --param product_category=2.86.285.396

  # Just show the filter/parameter map of the last page and exit:
  uv run finn/finn_search.py -q "pokemon kort" --print-filters

  # Parse an already-saved page offline (no network):
  uv run finn/finn_search.py --parse data/finn/_probe/search_pokemon_kort.html
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import finnlib as fl  # noqa: E402  (local sibling module)

# Queries we vary systematically (spec §1.5). Deliberately includes seller
# typos — that is where underpriced deals hide.
DEFAULT_QUERIES = [
    "pokemon kort",
    "pokémon kort",
    "vintage pokemon kort",
    "pokemon samling",
    "japanske pokemon kort",
    "pokemon kort holo",
]

# Sort values exposed by FINN (from the embedded sort filter scope).
SORT_VALUES = ["PUBLISHED_ASC", "PUBLISHED_DESC", "RELEVANCE", "PRICE_ASC", "PRICE_DESC", "CLOSEST"]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def build_url(query: str, sort: str, page: int, extra: list[tuple[str, str]]) -> str:
    """Build a FINN search URL from the query + full parameter map."""
    params: list[tuple[str, str]] = [("q", query), ("sort", sort)]
    params.extend(extra)
    if page and page > 1:
        params.append(("page", str(page)))
    return fl.SEARCH_HTML_URL + "?" + urllib.parse.urlencode(params)


def doc_record(doc: dict[str, Any], query: str, sort: str, page: int, run_id: str) -> dict[str, Any]:
    """Flatten an ad document into a stable row for JSONL/CSV consumers."""
    price = doc.get("price") or {}
    images = fl.max_image_urls(doc)
    labels = [l.get("text") for l in (doc.get("labels") or []) if isinstance(l, dict)]
    label_ids = [l.get("id") for l in (doc.get("labels") or []) if isinstance(l, dict)]
    return {
        "run_id": run_id,
        "scraped_at": fl.iso_now(),
        "query": query,
        "sort": sort,
        "page": page,
        "finn_kode": str(doc.get("ad_id") or doc.get("id") or ""),
        "heading": doc.get("heading"),
        "location": doc.get("location"),
        "trade_type": doc.get("trade_type"),
        "price_amount": price.get("amount"),
        "price_currency": price.get("currency_code"),
        "price_unit": price.get("price_unit"),
        "timestamp_ms": doc.get("timestamp"),
        "lat": (doc.get("coordinates") or {}).get("lat"),
        "lon": (doc.get("coordinates") or {}).get("lon"),
        "flags": doc.get("flags") or [],
        "labels": labels,
        "label_ids": label_ids,
        "image_count": len(images),
        "image_urls": images,
        "canonical_url": doc.get("canonical_url"),
        "ad_type": doc.get("ad_type"),
        "main_search_key": doc.get("main_search_key"),
        "metadata": doc.get("metadata") or {},
    }


def load_registry(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"    WARNING: could not read registry {path}: {exc!r}")
        return {}


def load_search_set(kind: str | None = None, tier: int | None = None,
                    ids: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """Load search definitions from the canonical catalog ``finn_searches.py``.

    This is the §3 of the program brief: the catalog *is* the search set. We import
    it lazily so plain ``-q`` runs never pay for it.
    """
    import finn_searches  # local sibling module (finn/ is on sys.path)
    return finn_searches.search_defs(kind, tier, ids)


def jobs_from_defs(
    defs: Iterable[dict[str, Any]],
    *,
    cli_sorts: list[str] | None,
    cli_max_pages: int | None,
    cli_extra: list[tuple[str, str]] | None,
) -> list[dict[str, Any]]:
    """Expand catalog search-defs into concrete fetch jobs.

    A job is one query with its own sorts, page budget and parameter list.  A def's
    own ``sorts``/``max_pages`` win; ``cli_sorts``/``cli_max_pages`` are only the
    fallback for ad-hoc ``-q`` defs (which carry ``None``).  ``cli_extra`` params are
    appended to every job.
    """
    extra = list(cli_extra or [])
    jobs: list[dict[str, Any]] = []
    for d in defs:
        sorts = list(d.get("sorts") or cli_sorts or ["PUBLISHED_DESC"])
        max_pages = int(d.get("max_pages") or cli_max_pages or 1)
        params = list(dict(d.get("params") or {}).items()) + extra
        jobs.append({
            "id": d.get("id"),
            "kind": d.get("kind"),
            "label": d.get("label"),
            "query": d["query"],
            "tier": d.get("tier"),
            "sorts": sorts,
            "max_pages": max_pages,
            "params": params,
        })
    return jobs


def compute_delta(known_before: Iterable[str], seen_now: Iterable[str]) -> dict[str, list[str]]:
    """Partition the registry change into ``new`` / ``still_active`` / ``gone``.

    ``known_before`` is the kode set recorded *before* this run's update; ``seen_now``
    is what this run observed.  The three groups are disjoint and their union is
    ``known_before | seen_now``.
    """
    before = set(known_before)
    now = set(seen_now)
    return {
        "new": sorted(now - before),
        "still_active": sorted(now & before),
        "gone": sorted(before - now),
    }


def run_parse_only(path: Path) -> int:
    """Parse an already-saved search HTML offline and dump its docs."""
    html = path.read_text(encoding="utf-8")
    state = fl.parse_search_state(html)
    docs = state["docs"]
    meta = state["metadata"]
    print(f"blocks={state['blocks']}  docs={len(docs)}  num_results={meta.get('num_results')}")
    print("paging:", meta.get("paging"), " match_count:", (meta.get("result_size") or {}).get("match_count"))
    out = fl.unique_path(path.with_suffix(".docs.jsonl"))
    for d in docs:
        fl.append_jsonl(out, d)
    print(f"wrote {len(docs)} docs -> {out}")
    # show a couple
    for d in docs[:3]:
        p = (d.get("price") or {}).get("amount")
        print(f"  {d.get('ad_id')}  {p} kr  {d.get('heading')}  [{d.get('location')}]")
    return 0


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-q", "--query", action="append", dest="queries", metavar="TEXT",
                        help="search term (repeatable). Default: a built-in query list.")
    parser.add_argument("--search-set", action="store_true",
                        help="run the canonical catalog in finn_searches.py (the recommended mode). "
                             "Each definition supplies its own query, params, sorts and page budget.")
    parser.add_argument("--kind", choices=["broad", "set", "card", "all"], default=None,
                        help="with --search-set: only this kind of search")
    parser.add_argument("--tier", type=int, choices=[1, 2], default=None,
                        help="with --search-set: only set-searches of this tier")
    parser.add_argument("--id", action="append", dest="ids", default=None, metavar="SEARCH_ID",
                        help="with --search-set: only these catalog ids (repeatable)")
    parser.add_argument("--sort", default="PUBLISHED_DESC",
                        help=f"comma-separated sorts from {SORT_VALUES} (default PUBLISHED_DESC). "
                             f"Applies only to ad-hoc -q queries; catalog defs keep their own sorts.")
    parser.add_argument("--max-pages", type=int, default=1,
                        help="max pages per (query,sort) for ad-hoc -q queries (default 1). "
                             "Catalog defs keep their own page budget.")
    parser.add_argument("--all-pages", action="store_true",
                        help="fetch every page FINN reports (up to paging.last)")
    parser.add_argument("--param", action="append", default=[], metavar="KEY=VALUE",
                        help="extra search parameter (repeatable), e.g. --param sub_category=1.86.285")
    parser.add_argument("--delay", type=float, default=2.0, help="base delay between requests (s)")
    parser.add_argument("--jitter", type=float, default=1.5, help="random jitter added to delay (s)")
    parser.add_argument("--outdir", default=str(fl.DATA_FINN / "searches"),
                        help="run output root (default data/finn/searches)")
    parser.add_argument("--dry-run", action="store_true", help="print the URLs; do not fetch")
    parser.add_argument("--print-filters", action="store_true",
                        help="print the embedded filter/parameter map after the first page and exit")
    parser.add_argument("--no-registry", action="store_true",
                        help="do not update the per-query seen-kode registry / delta report")
    parser.add_argument("--parse", metavar="HTML", help="offline: parse an existing search HTML and exit")
    args = parser.parse_args(argv)

    # ---- offline parse mode ----
    if args.parse:
        return run_parse_only(Path(args.parse))

    # ---- resolve the search set: canonical catalog and/or ad-hoc -q queries ----
    defs: list[dict[str, Any]] = []
    if args.search_set:
        defs += load_search_set(kind=args.kind, tier=args.tier, ids=args.ids)
        if not defs:
            print("ERROR: --search-set selected 0 searches (check --kind/--tier/--id)")
            return 2
    for q in (args.queries or ([] if args.search_set else DEFAULT_QUERIES)):
        defs.append({"id": f"query-{fl.slugify(q)}", "kind": "query", "label": q,
                     "query": q, "tier": None, "params": {}, "sorts": None, "max_pages": None})

    cli_extra: list[tuple[str, str]] = []
    for p in args.param:
        if "=" not in p:
            print(f"ERROR: --param needs KEY=VALUE, got {p!r}")
            return 2
        k, v = p.split("=", 1)
        cli_extra.append((k, v))

    cli_sorts = [s.strip().upper() for s in args.sort.split(",") if s.strip()]
    for s in cli_sorts:
        if s not in SORT_VALUES:
            print(f"WARNING: sort {s!r} is not in the known set {SORT_VALUES} — sending anyway.")

    jobs = jobs_from_defs(defs, cli_sorts=cli_sorts, cli_max_pages=args.max_pages,
                          cli_extra=cli_extra)

    # ---- dry run: plan + print only; no network, no writes ----
    if args.dry_run:
        total_pages = 0
        print("=" * 88)
        print(f"FINN search DRY RUN  jobs={len(jobs)}  (no network, no files written)")
        print("=" * 88)
        for job in jobs:
            for sort in job["sorts"]:
                for page in range(1, job["max_pages"] + 1):
                    print(f"[{job['id']} | {job['query']} | {sort} | page {page}] "
                          f"{build_url(job['query'], sort, page, job['params'])}")
                    total_pages += 1
        print("=" * 88)
        print(f"DRY RUN: jobs={len(jobs)}  planned_pages={total_pages}  files_written=0")
        return 0

    run_id = fl.ts_now()
    run_dir = fl.ensure_dir(Path(args.outdir) / run_id)
    log_dir = fl.ensure_dir(fl.DATA_FINN / "_log")
    reg_dir = fl.ensure_dir(fl.DATA_FINN / "registry")

    print("=" * 88)
    print(f"FINN search run {run_id}  jobs={len(jobs)}")
    print(f"  queries : {[j['query'] for j in jobs]}")
    print(f"  searches: {[j['id'] for j in jobs]}")
    print(f"  extra   : {cli_extra}   all_pages={args.all_pages}")
    print(f"  outdir  : {run_dir}")
    print("=" * 88)

    run_manifest: dict[str, Any] = {
        "run_id": run_id,
        "started_at": fl.iso_now(),
        "search_set": bool(args.search_set),
        "queries": [j["query"] for j in jobs],
        "searches": [
            {"id": j["id"], "kind": j["kind"], "label": j["label"], "query": j["query"],
             "tier": j["tier"], "sorts": j["sorts"], "max_pages": j["max_pages"],
             "params": j["params"]}
            for j in jobs
        ],
        "extra_params": cli_extra,
        "all_pages": args.all_pages,
        "dry_run": False,
        "pages": [],
        "totals": {"pages": 0, "docs": 0},
    }

    combined_path = run_dir / "all_ads.jsonl"
    filters_written = False
    grand_new: set[str] = set()

    # group jobs by query so defs that share a query share one registry + delta
    groups: dict[str, list[dict[str, Any]]] = {}
    for job in jobs:
        groups.setdefault(job["query"], []).append(job)

    for query, qjobs in groups.items():
        q_slug = fl.slugify(query)
        q_dir = fl.ensure_dir(run_dir / q_slug)
        registry_path = reg_dir / f"{q_slug}.json"
        loaded = {} if args.no_registry else load_registry(registry_path)
        known_before = set(loaded)
        registry: dict[str, dict[str, Any]] = {k: dict(v) for k, v in loaded.items()}
        seen_this_query: set[str] = set()

        for job in qjobs:
            params = job["params"]
            for sort in job["sorts"]:
                page = 1
                last_page = job["max_pages"]
                while page <= last_page:
                    url = build_url(query, sort, page, params)
                    print(f"\n[{job['id']} | {query} | {sort} | page {page}] {url}")

                    status, body, _hdrs = fl.http_get(
                        url, retries=3, base_delay=args.delay, jitter=args.jitter
                    )
                    html = body.decode("utf-8", errors="replace")
                    raw_path = fl.unique_path(q_dir / f"page_{page:03d}.html")
                    raw_path.write_text(html, encoding="utf-8")
                    print(f"    raw -> {raw_path} ({len(html)} chars)")

                    try:
                        state = fl.parse_search_state(html)
                    except ValueError as exc:
                        print(f"    PARSE FAILED: {exc}")
                        fl.append_jsonl(log_dir / "search_pages.jsonl", {
                            "run_id": run_id, "scraped_at": fl.iso_now(), "query": query,
                            "sort": sort, "page": page, "status": str(status),
                            "error": str(exc), "raw_path": str(raw_path),
                        })
                        break

                    docs = state["docs"]
                    meta = state["metadata"]
                    paging = meta.get("paging") or {}
                    match_count = (meta.get("result_size") or {}).get("match_count")

                    # verify docs vs advertised num_results (no silent truncation)
                    num_results = meta.get("num_results")
                    if num_results is not None and len(docs) != num_results and page < (paging.get("last") or 1):
                        print(f"    NOTE: docs={len(docs)} != num_results={num_results}")

                    # write parsed docs
                    docs_path = q_dir / f"page_{page:03d}.docs.jsonl"
                    for d in docs:
                        rec = doc_record(d, query, sort, page, run_id)
                        fl.append_jsonl(docs_path, rec)
                        fl.append_jsonl(combined_path, rec)
                        fl.append_jsonl(log_dir / "ads_seen.jsonl", rec)
                        kode = rec["finn_kode"]
                        seen_this_query.add(kode)
                        if not args.no_registry:
                            entry = registry.get(kode, {"first_seen": rec["scraped_at"]})
                            entry["last_seen"] = rec["scraped_at"]
                            entry["last_price"] = rec["price_amount"]
                            entry["heading"] = rec["heading"]
                            registry[kode] = entry

                    # the complete filter/parameter map (write once per run)
                    if state["filters"] and not filters_written:
                        fl.write_json(run_dir / "filters.json", state["filters"])
                        fl.write_json(fl.unique_path(fl.DATA_FINN / "filters" / f"filters_{run_id}.json"),
                                      state["filters"])
                        filters_written = True
                        if args.print_filters:
                            print("\n--- FINN filter / parameter map ---")
                            for f in state["filters"]:
                                name = f.get("name")
                                items = f.get("filter_items") or []
                                print(f"  {name:16s} type={f.get('type')} items={len(items)}")
                                for it in items[:6]:
                                    print(f"      {it.get('value')!s:22s} hits={it.get('hits')}  {it.get('display_name')}")
                            print("--- end filter map ---\n")
                            fl.write_json(run_dir / "run.json", run_manifest)
                            return 0

                    print(f"    docs={len(docs)}  num_results={num_results}  "
                          f"match_count={match_count}  paging={paging}")
                    fl.append_jsonl(log_dir / "search_pages.jsonl", {
                        "run_id": run_id, "scraped_at": fl.iso_now(), "query": query, "sort": sort,
                        "page": page, "status": status, "docs": len(docs), "num_results": num_results,
                        "match_count": match_count, "paging": paging, "raw_path": str(raw_path),
                    })
                    run_manifest["pages"].append({
                        "query": query, "sort": sort, "page": page, "url": url,
                        "status": status, "docs": len(docs), "num_results": num_results,
                        "match_count": match_count, "paging": paging, "raw": str(raw_path),
                    })
                    run_manifest["totals"]["pages"] += 1
                    run_manifest["totals"]["docs"] += len(docs)

                    # decide whether to continue
                    if args.all_pages:
                        last_page = min(paging.get("last") or page, 10_000)
                        if meta.get("is_end_of_paging") or page >= last_page:
                            if page < (paging.get("last") or page):
                                print(f"    stopping: reached paging.last={paging.get('last')}")
                            break
                    page += 1
                    time.sleep(args.delay + random.uniform(0, args.jitter))

        # ---- delta report + registry persist ----
        if not args.no_registry:
            delta = compute_delta(known_before, seen_this_query)
            grand_new |= set(delta["new"])
            fl.write_json(registry_path, dict(sorted(registry.items())))
            print(f"\n[{query}] delta: new={len(delta['new'])}  "
                  f"still_active={len(delta['still_active'])}  gone={len(delta['gone'])}  "
                  f"seen={len(seen_this_query)}  known_before={len(known_before)}")
            fl.append_jsonl(log_dir / "delta.jsonl", {
                "run_id": run_id, "scraped_at": fl.iso_now(), "query": query,
                "new": delta["new"], "still_active": delta["still_active"], "gone": delta["gone"],
                "seen": len(seen_this_query), "known_before": len(known_before),
                "known_after": len(registry),
            })

    run_manifest["finished_at"] = fl.iso_now()
    run_manifest["total_new_koder"] = len(grand_new)
    fl.write_json(run_dir / "run.json", run_manifest)

    print("\n" + "=" * 88)
    print(f"DONE  run={run_id}  pages={run_manifest['totals']['pages']}  "
          f"docs={run_manifest['totals']['docs']}  new_koder={len(grand_new)}")
    print(f"  combined ads : {combined_path}")
    print(f"  manifest     : {run_dir / 'run.json'}")
    print("=" * 88)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
