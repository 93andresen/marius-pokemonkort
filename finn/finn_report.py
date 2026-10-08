#!/usr/bin/env python3
"""Count what actually flowed through the FINN pipeline (a coverage report).

This stage is **pure accounting** — no scraping, no pricing, no network.  It
reads the append-only artifacts the earlier stages wrote and emits an honest
coverage report (machine JSON + a short Markdown), so the program's finished
state is *demonstrated, not asserted*:

* ``data/finn/registry/pokemon-kort.json``  — discovered ads (unique FINN-koder)
* ``data/finn/searches/*/run.json``          — search runs, pages, docs seen
* ``data/finn/searches/*/all_ads.jsonl``     — latest discovery set (intent ranks)
* ``data/finn/matches/matches.jsonl``        — listing-level match overlays
* ``data/finn/matches/pricing.jsonl``        — per-ad / per-card prices + deal ratio
* ``data/finn/annonser/*``                   — ads fully archived (raw + parsed + photos)

A missing artifact yields zeros and a note, never a crash.

Run::

    uv run finn/finn_report.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent))  # finn/

import finn_identify as fi  # noqa: E402
import finnlib as fl  # noqa: E402

REPORT_VERSION = "finn_report/1.0.0"

DATA_FINN = fl.DATA_FINN
DEFAULT_REGISTRY = DATA_FINN / "registry" / "pokemon-kort.json"
DEFAULT_SEARCHES = DATA_FINN / "searches"
DEFAULT_MATCHES = DATA_FINN / "matches" / "matches.jsonl"
DEFAULT_PRICING = DATA_FINN / "matches" / "pricing.jsonl"
DEFAULT_ANNONSER = DATA_FINN / "annonser"
DEFAULT_OUTDIR = DATA_FINN / "reports"


def log(message: str) -> None:
    """Progress goes to stderr so ``--json`` stdout stays machine-parseable."""
    print(message, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- #
# artifact readers
# --------------------------------------------------------------------------- #


def _read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    # JSONL is "\n"-delimited: splitlines() breaks on U+2028/U+2029 too.
    for line in p.read_text(encoding="utf-8").split("\n"):
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def count_registry(path: Path | str) -> dict[str, Any]:
    """Unique discovered FINN-koder + seen window, from the registry JSON."""
    p = Path(path)
    notes: list[str] = []
    if not p.exists():
        notes.append(f"registry missing: {p}")
        return {"koder": 0, "first_seen": None, "last_seen": None, "notes": notes}
    data = json.loads(p.read_text(encoding="utf-8"))
    firsts = [str(v.get("first_seen")) for v in data.values() if v.get("first_seen")]
    lasts = [str(v.get("last_seen")) for v in data.values() if v.get("last_seen")]
    return {
        "koder": len(data),
        "first_seen": min(firsts) if firsts else None,
        "last_seen": max(lasts) if lasts else None,
        "notes": notes,
    }


def count_runs(searches_dir: Path | str) -> dict[str, Any]:
    """Search runs + total pages / docs, from each ``*/run.json``."""
    base = Path(searches_dir)
    notes: list[str] = []
    runs = pages = docs = 0
    if not base.exists():
        notes.append(f"searches dir missing: {base}")
        return {"runs": 0, "pages": 0, "docs": 0, "notes": notes}
    for run_json in sorted(base.glob("*/run.json")):
        try:
            run = json.loads(run_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:  # never hide a broken artifact
            notes.append(f"unreadable {run_json}: {exc}")
            continue
        totals = run.get("totals") or {}
        runs += 1
        pages += int(totals.get("pages") or 0)
        docs += int(totals.get("docs") or 0)
    return {"runs": runs, "pages": pages, "docs": docs, "notes": notes}


def count_matches(path: Path | str) -> dict[str, Any]:
    """Listing-overlay records + how many resolved to a card (``best`` non-null)."""
    rows = _read_jsonl(path)
    matched = sum(1 for r in rows if r.get("best"))
    notes = [] if rows else ["no match overlays recorded yet"]
    return {"records": len(rows), "matched": matched, "notes": notes}


def count_pricing(path: Path | str) -> dict[str, Any]:
    """Priced ads + how many carry a market value / deal ratio, and card sums."""
    rows = _read_jsonl(path)
    with_value = 0
    with_ratio = 0
    basis: dict[str, int] = {}
    cards_total = 0
    cards_priced = 0
    for r in rows:
        deal = r.get("deal") or {}
        if deal.get("market_value_nok") is not None:
            with_value += 1
        if deal.get("ratio") is not None:
            with_ratio += 1
        b = str(deal.get("basis") or "none")
        basis[b] = basis.get(b, 0) + 1
        cov = r.get("card_coverage") or {}
        cards_total += int(cov.get("total") or 0)
        cards_priced += int(cov.get("priced") or 0)
    notes: list[str] = []
    if not rows:
        notes.append("no pricing records yet")
    elif cards_total and cards_priced == 0:
        notes.append(f"{cards_total} card(s) enumerated but none priced "
                     "(cache cold / budget)")
    return {
        "records": len(rows),
        "with_value": with_value,
        "with_ratio": with_ratio,
        "basis": basis,
        "cards_total": cards_total,
        "cards_priced": cards_priced,
        "notes": notes,
    }


def count_archive(annonser_dir: Path | str) -> dict[str, Any]:
    """Fully archived ads (one per subdirectory of ``annonser/``)."""
    base = Path(annonser_dir)
    if not base.exists():
        return {"ads": 0, "notes": [f"annonser dir missing: {base}"]}
    ads = sum(1 for child in base.iterdir() if child.is_dir())
    return {"ads": ads, "notes": []}


def latest_ads(searches_dir: Path | str) -> list[dict[str, Any]]:
    """Discovery rows from the newest search run that wrote ``all_ads.jsonl``."""
    base = Path(searches_dir)
    if not base.exists():
        return []
    candidates = sorted(
        (d for d in base.iterdir() if (d / "all_ads.jsonl").exists()),
        key=lambda d: d.name,
    )
    return _read_jsonl(candidates[-1] / "all_ads.jsonl") if candidates else []


def intent_distribution(ads: list[dict[str, Any]]) -> dict[str, int]:
    """Count ads per ``finn_identify`` intent label, deduped by ``finn_kode``."""
    counts: dict[str, int] = {}
    seen: set[str] = set()
    for ad in ads:
        kode = str(ad.get("finn_kode") or "")
        if kode and kode in seen:
            continue
        if kode:
            seen.add(kode)
        label = str(fi.identify_ad(ad).get("intent") or "none")
        counts[label] = counts.get(label, 0) + 1
    counts["total"] = len(seen) if seen else len(ads)
    return counts


# --------------------------------------------------------------------------- #
# composition
# --------------------------------------------------------------------------- #


def coverage(*, registry: Path | str, searches_dir: Path | str,
             matches: Path | str, pricing: Path | str,
             annonser: Path | str) -> dict[str, Any]:
    """Compose every stage's counts into one coverage dict."""
    disc = count_registry(registry)
    runs = count_runs(searches_dir)
    arch = count_archive(annonser)
    mt = count_matches(matches)
    pr = count_pricing(pricing)
    ident = intent_distribution(latest_ads(searches_dir))

    notes = list(disc["notes"] + runs["notes"] + arch["notes"] + mt["notes"] + pr["notes"])
    if disc["koder"] and arch["ads"] < disc["koder"]:
        notes.append(f"only {arch['ads']} of {disc['koder']} discovered ads are archived")

    return {
        "report_version": REPORT_VERSION,
        "generated_at": fl.iso_now(),
        "discovery": {
            "koder": disc["koder"],
            "first_seen": disc["first_seen"],
            "last_seen": disc["last_seen"],
            "runs": runs["runs"],
            "pages": runs["pages"],
            "docs": runs["docs"],
        },
        "archive": {
            "ads_archived": arch["ads"],
            "koder_discovered": disc["koder"],
        },
        "identify": ident,
        "match": {"records": mt["records"], "matched": mt["matched"]},
        "pricing": {
            "records": pr["records"],
            "with_value": pr["with_value"],
            "with_ratio": pr["with_ratio"],
            "basis": pr["basis"],
            "cards_total": pr["cards_total"],
            "cards_priced": pr["cards_priced"],
        },
        "notes": notes,
    }


def render_markdown(cov: dict[str, Any]) -> str:
    """A short, readable coverage report. Every line is a real count."""
    d = cov["discovery"]
    a = cov["archive"]
    ident = cov["identify"]
    m = cov["match"]
    p = cov["pricing"]

    lines = [
        "# FINN Pokemon coverage report",
        "",
        f"_generated {cov['generated_at']} · {cov['report_version']}_",
        "",
        "## Discovery",
        f"- unique ads in registry: **{d['koder']}**",
        f"- search runs: {d['runs']}  ·  pages fetched: {d['pages']}  ·  docs seen: {d['docs']}",
        f"- seen window: {d['first_seen']} → {d['last_seen']}",
        "",
        "## Archive",
        f"- ads fully archived: **{a['ads_archived']}** of {a['koder_discovered']} discovered",
        "",
        "## Identify",
        f"- ads ranked (latest discovery set): **{ident.get('total', 0)}**",
    ]
    for label in sorted(k for k in ident if k != "total"):
        lines.append(f"  - {label}: {ident[label]}")
    lines += [
        "",
        "## Match",
        f"- listing overlays: {m['records']}  ·  resolved to a card: **{m['matched']}**",
        "",
        "## Pricing",
        f"- priced ads: {p['records']}  ·  with a market value: **{p['with_value']}**  ·  "
        f"with a deal ratio: **{p['with_ratio']}**",
        f"- basis: {p['basis']}",
        f"- enumerated cards: {p['cards_total']}  ·  priced: **{p['cards_priced']}**",
        "",
    ]
    if cov["notes"]:
        lines.append("## Notes / gaps")
        lines += [f"- {n}" for n in cov["notes"]]
        lines.append("")
    return "\n".join(lines)


def build(cov: dict[str, Any], outdir: Path | str, *,
          ts: str | None = None) -> dict[str, Any]:
    """Write ``coverage_<ts>.json`` + ``coverage_<ts>.md``; return the paths."""
    ts = ts or fl.ts_now()
    out = fl.ensure_dir(outdir)
    json_path = fl.unique_path(out / f"coverage_{ts}.json")
    md_path = fl.unique_path(out / f"coverage_{ts}.md")
    json_path.write_text(json.dumps(cov, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    md_path.write_text(render_markdown(cov), encoding="utf-8")
    return {"ts": ts, "json": str(json_path), "markdown": str(md_path)}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--searches-dir", default=str(DEFAULT_SEARCHES))
    parser.add_argument("--matches", default=str(DEFAULT_MATCHES))
    parser.add_argument("--pricing", default=str(DEFAULT_PRICING))
    parser.add_argument("--annonser", default=str(DEFAULT_ANNONSER))
    parser.add_argument("--outdir", default=str(DEFAULT_OUTDIR))
    parser.add_argument("--ts", default=None, help="timestamp for filenames (default: now)")
    parser.add_argument("--json", action="store_true",
                        help="print the coverage dict as JSON on stdout")
    args = parser.parse_args(argv)

    cov = coverage(
        registry=args.registry, searches_dir=args.searches_dir,
        matches=args.matches, pricing=args.pricing, annonser=args.annonser,
    )
    paths = build(cov, args.outdir, ts=args.ts)

    log("=" * 88)
    log(f"FINN coverage  |  ts={paths['ts']}")
    log("=" * 88)
    log(f"  discovered koder : {cov['discovery']['koder']}  "
        f"(runs={cov['discovery']['runs']} pages={cov['discovery']['pages']} "
        f"docs={cov['discovery']['docs']})")
    log(f"  archived ads     : {cov['archive']['ads_archived']}")
    log(f"  matched listings : {cov['match']['matched']}/{cov['match']['records']}")
    log(f"  priced ads       : {cov['pricing']['records']}  "
        f"with_value={cov['pricing']['with_value']} "
        f"with_ratio={cov['pricing']['with_ratio']}")
    log(f"  cards            : {cov['pricing']['cards_priced']}/"
        f"{cov['pricing']['cards_total']} priced")
    for note in cov["notes"]:
        log(f"  NOTE: {note}")
    log(f"  report -> {paths['markdown']}")
    log(f"  json   -> {paths['json']}")
    log("=" * 88)

    if args.json:
        print(json.dumps(cov, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
