#!/usr/bin/env python3
"""fetch_prices.py — append-only price snapshots for the Collectr portfolio.

Why per-card ``/search`` (verified live 2026-10-02, see
``docs/pokewallet_io_api-VERIFIED-NOTES.md``):

* ``GET /sets/:code`` returns the cards but with **empty** price arrays on the
  free plan, so it cannot be used for pricing.
* ``GET /cards/:id`` returns prices, but we only learn the id from a set call.
* ``GET /search`` with ``q="<key> <card_number>"`` returns the card **with**
  TCGPlayer/CardMarket prices. The docs recommend ``set_id`` as the key, which
  is exact for positive ids, but several sets have **negative** ids (e.g. LOT
  = ``-113``) for which the id query returns unrelated cards that merely share
  the number. So we try several keys (id -> code -> name) and *validate every
  candidate* before trusting it (see :func:`validate_match`). One card -> one
  to three calls, usually one.

Design guarantees (per PROJECT-PLAN.md / AGENTS.md):

* **Never overwrite / never lose data** — one JSON object per portfolio row is
  *appended* to ``snapshots/portfolio_prices.jsonl`` (flushed + fsynced), and a
  flat ``snapshots/snapshot_<run_id>.csv`` is written for the sheet.
* **Resumable & rate-aware** — cards already fetched within ``--fresh-hours``
  (default 20h) are served from the append-only JSONL instead of spending a new
  call, so a run stopped at the budget floor simply continues next time. Unique
  cards are deduped so shared cards cost once.
* **No silent success** — every failure (missing key, HTTP error, no result) is
  printed and recorded; nothing is hidden.

    uv run pokewallet/fetch_prices.py               # full portfolio snapshot
    uv run pokewallet/fetch_prices.py --limit 20    # first 20 unique cards
    uv run pokewallet/fetch_prices.py --only-set SSP
    uv run pokewallet/fetch_prices.py --dry-run     # show plan, no calls
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from pwlib import config, portfolio, prices as pricelib, sets as setslib
from pwlib.api import BudgetExhausted, MissingApiKey, PokeWalletClient
from pwlib.util import append_jsonl, ensure_dir, now_ts, unique_path, utc_iso

# Import the index loader written for the resolver (same directory).
from resolve_portfolio import load_index

SNAPSHOT_HEADER = [
    "run_id", "run_ts_utc", "row_index", "portfolio", "category",
    "set", "set_code", "set_id", "api_set_name",
    "number", "number_norm", "product_name", "rarity", "variance", "grade",
    "condition", "quantity", "avg_cost_paid_nok", "collectr_market_nok",
    "watchlist", "date_added",
    "pk_id", "pk_name", "pk_set_name", "pk_set_code", "pk_card_number", "pk_rarity",
    "tcg_market", "tcg_low", "tcg_mid", "tcg_high", "tcg_subtype", "tcg_updated",
    "tcgplayer_url",
    "cmk_trend", "cmk_avg", "cmk_low", "cmk_variant", "cmk_updated",
    "price_source", "found", "served_from", "match_method", "candidate", "query",
]

SNAPSHOT_JSONL = config.SNAPSHOTS_DIR / "portfolio_prices.jsonl"

# Fields rebuilt from the Collectr CSV + set index on every run. Everything else
# in SNAPSHOT_HEADER comes from the API and is therefore *carried forward* from
# the most recent snapshot when a card is served from cache (skip) or when a
# fresh fetch fails — so the flat CSV always shows the best known state and no
# run ever loses a previously-known price.
PORTFOLIO_FIELDS = {
    "run_id", "run_ts_utc", "row_index", "portfolio", "category",
    "set", "set_code", "set_id", "api_set_name", "number", "number_norm",
    "product_name", "rarity", "variance", "grade", "condition", "quantity",
    "avg_cost_paid_nok", "collectr_market_nok", "watchlist", "date_added",
}
CACHE_FIELDS = [
    c for c in SNAPSHOT_HEADER
    if c not in PORTFOLIO_FIELDS and c != "served_from"
]


# --- payload helpers -------------------------------------------------------
def search_results(payload: object) -> list[dict]:
    """Extract the list of card dicts from a ``/search`` response."""
    if isinstance(payload, dict):
        for key in ("results", "data", "cards"):
            value = payload.get(key)
            if isinstance(value, list):
                return [c for c in value if isinstance(c, dict)]
    if isinstance(payload, list):
        return [c for c in payload if isinstance(c, dict)]
    return []


def _info(card: dict) -> dict:
    """The ``card_info`` block, or the card itself if it is already flat."""
    return card.get("card_info") or card


def _base_name(value: object) -> str:
    """Reduce a name to its bare card name for comparison.

    The API's ``card_info.name`` is often ``"<name> - <number> (<set>)"``
    (e.g. ``"Roaring Moon ex - 090/066"``, ``"Shelgon - 054/113 (Delta
    Species)"``), while Collectr stores ``"Roaring Moon ex (JP)"``. So we drop
    everything from the first ``" - "`` and remove any remaining ``(...)``
    hints, then apply the shared name normalisation (lowercase,
    punctuation-stripped, whitespace-collapsed).
    """
    text = str(value or "").split(" - ", 1)[0]
    text = re.sub(r"\([^)]*\)", " ", text)
    return setslib.normalize_name(text)


def validate_match(
    card: dict,
    number_norm: str,
    expected_name: str,
    set_id: str,
    set_code: str,
) -> str | None:
    """Return a match label if ``card`` is a *trustworthy* hit, else ``None``.

    A candidate is only accepted when the card number agrees **and** at least
    one independent identity signal agrees:

    * the card name (parenthetical-stripped, normalised) is identical
      (``name_number``), or
    * the card's set code / set id equals the expected one (``set_number``).

    Requiring the *name* is what stops the free-text ``/search`` from matching
    an unrelated card that merely shares a number. Verified bug (2026-10-02):
    ``Lost Thunder #54 Slowpoke`` used to match ``Shelgon 054/113 (Delta
    Species)``, and ``Wild Force #80 Gastly`` matched ``Medicham ex 080/142``.
    A wrong match silently corrupts the portfolio, so an unmatched card is
    always preferred over a confidently-wrong one (see D7 in PROJECT-PLAN.md).
    """
    info = _info(card)
    if portfolio.number_norm(info.get("card_number")) != number_norm:
        return None
    got_name = _base_name(info.get("name"))
    exp_name = _base_name(expected_name)
    if exp_name and got_name and got_name == exp_name:
        return "name_number"
    got_code = str(info.get("set_code") or "").strip().lower()
    got_id = str(info.get("set_id") or "").strip()
    if set_code and got_code == str(set_code).strip().lower():
        return "set_number"
    if set_id and got_id == str(set_id).strip():
        return "set_number"
    return None


def pick_card(
    results: list[dict],
    number_norm: str,
    expected_name: str,
    set_id: str,
    set_code: str,
) -> tuple[dict | None, str]:
    """First result passing :func:`validate_match`; else ``(None, "reject")``."""
    for card in results:
        label = validate_match(card, number_norm, expected_name, set_id, set_code)
        if label:
            return card, label
    return (None, "reject") if results else (None, "none")


def candidate_summary(card: dict) -> str:
    """Compact ``name | number | set`` string for an unvalidated candidate."""
    info = _info(card)
    return " | ".join([
        str(info.get("name") or ""),
        str(info.get("card_number") or ""),
        str(info.get("set_code") or ""),
    ])


def numerator(raw: object) -> str:
    """The number part before ``/`` exactly as written (e.g. ``048``)."""
    return str(raw or "").strip().split("/")[0].strip()


# --- resume helpers --------------------------------------------------------
def age_hours(ts_iso: object) -> float | None:
    """Hours between ``ts_iso`` (UTC ``...Z``) and now; ``None`` if unparsable."""
    text = str(ts_iso or "")
    if not text:
        return None
    try:
        when = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - when).total_seconds() / 3600.0


def load_latest_snapshots(path: Path) -> dict[tuple[str, str], dict]:
    """Newest appended record per ``(set_id, number_norm)`` from the JSONL.

    This is what makes the fetcher *truly* resumable: instead of re-spending the
    scarce free-plan budget on cards we already resolved, we read what we have
    and only fetch the gaps. Malformed lines are skipped, never fatal.
    """
    latest: dict[tuple[str, str], dict] = {}
    if not Path(path).exists():
        return latest
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict):
                continue
            set_id = str(rec.get("set_id") or "")
            number_norm = str(rec.get("number_norm") or "")
            if not set_id or not number_norm:
                continue
            key = (set_id, number_norm)
            prev = latest.get(key)
            if prev is None or (rec.get("run_ts_utc") or "") >= (prev.get("run_ts_utc") or ""):
                latest[key] = rec
    return latest


def carry_forward(record: dict, cached: dict | None) -> bool:
    """Copy API-derived fields from ``cached`` into ``record``.

    Returns ``True`` when the cached record actually held a price (``found``),
    i.e. the record can be shown as a previously-known value. ``served_from`` is
    deliberately never copied — the caller sets the current run's label.
    """
    if not cached:
        return False
    for col in CACHE_FIELDS:
        if col in cached:
            record[col] = cached[col]
    return bool(cached.get("found"))


# --- main ------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=str(config.COLLECTR_CSV),
                        help="path to the Collectr export CSV")
    parser.add_argument("--limit", type=int, default=None,
                        help="fetch at most N unique cards this run")
    parser.add_argument("--only-set", default=None,
                        help="restrict to a single set_code (e.g. SSP)")
    parser.add_argument("--max-calls", type=int, default=0,
                        help="hard cap on API calls this run (0 = unlimited)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan without sending any requests")
    parser.add_argument("--force", action="store_true",
                        help="ignore the rate-budget safety floor")
    parser.add_argument("--fresh-hours", type=float, default=20.0,
                        help="skip cards already fetched within N hours "
                             "(0 = always refetch; default 20)")
    args = parser.parse_args(argv)

    fieldnames, rows = portfolio.read_rows(args.csv)
    market_col = portfolio.market_column(fieldnames)
    index = load_index()

    run_id = now_ts()
    run_ts_utc = utc_iso()

    # --- resolve rows to their set, then dedupe by (set_id, number_norm) ---
    # key -> list of per-row records (many rows can share one card)
    unique: dict[tuple[str, str], list[dict]] = {}
    orphan_rows: list[dict] = []  # rows with no set match / no number

    for i, row in enumerate(rows, start=1):
        set_name = (row.get(portfolio.SET_COL) or "").strip()
        number_raw = row.get(portfolio.NUMBER_COL)
        entry, set_method = setslib.lookup(index, set_name)

        record = {
            "run_id": run_id,
            "run_ts_utc": run_ts_utc,
            "row_index": i,
            "portfolio": row.get(portfolio.PORTFOLIO_COL, ""),
            "category": row.get(portfolio.CATEGORY_COL, ""),
            "set": set_name,
            "set_code": (entry or {}).get("set_code", ""),
            "set_id": (entry or {}).get("set_id", ""),
            "api_set_name": (entry or {}).get("name", ""),
            "number": number_raw,
            "number_norm": portfolio.number_norm(number_raw),
            "product_name": row.get(portfolio.NAME_COL, ""),
            "rarity": row.get(portfolio.RARITY_COL, ""),
            "variance": row.get(portfolio.VARIANCE_COL, ""),
            "grade": row.get(portfolio.GRADE_COL, ""),
            "condition": row.get(portfolio.CONDITION_COL, ""),
            "quantity": portfolio.parse_quantity(row.get(portfolio.QTY_COL)),
            "avg_cost_paid_nok": portfolio.parse_money(row.get(portfolio.COST_COL)),
            "collectr_market_nok": (
                portfolio.parse_money(row.get(market_col)) if market_col else None
            ),
            "watchlist": row.get(portfolio.WATCHLIST_COL, ""),
            "date_added": row.get(portfolio.DATE_ADDED_COL, ""),
            "set_match": set_method,
            "found": False,
            "match_method": f"set:{set_method}",
            "query": "",
        }
        set_id = record["set_id"]
        number_norm = record["number_norm"]
        if entry and set_id and number_norm:
            if args.only_set and record["set_code"].lower() != args.only_set.lower():
                orphan_rows.append(record)  # filtered out, not an error
                continue
            unique.setdefault((str(set_id), number_norm), []).append(record)
        else:
            orphan_rows.append(record)

    # --- resume: classify every card as already-fresh vs. needs-fetch ------
    latest = load_latest_snapshots(SNAPSHOT_JSONL)

    def is_fresh(key: tuple[str, str]) -> bool:
        cached = latest.get(key)
        if not cached or not cached.get("found") or args.fresh_hours <= 0:
            return False
        age = age_hours(cached.get("run_ts_utc"))
        return age is not None and age <= args.fresh_hours

    all_keys = sorted(unique)
    fresh_keys = [k for k in all_keys if is_fresh(k)]
    fetch_keys = [k for k in all_keys if not is_fresh(k)]
    if args.limit:
        fetch_keys = fetch_keys[: args.limit]

    print(f"run_id:               {run_id}")
    print(f"portfolio rows:       {len(rows)}")
    print(f"rows w/o set/no number: {len(orphan_rows)}")
    print(f"unique cards total:   {len(all_keys)}")
    print(f"  served from cache:  {len(fresh_keys)} (fetched < {args.fresh_hours:g}h ago)")
    print(f"  to fetch this run:  {len(fetch_keys)}")

    if args.dry_run:
        for key in fetch_keys:
            sample = unique[key][0]
            num_padded = numerator(sample["number"]) or key[1]
            api_name = sample.get("api_set_name") or sample["set"]
            queries = list(dict.fromkeys([
                f"{sample['set_id']} {num_padded}",
                f"{sample['set_code']} {num_padded}",
                f"{api_name} {num_padded}",
            ]))
            print(f"  [{sample['set_code']}] {sample['set']!r} #{sample['number']} -> "
                  + "  ".join(f"q={q!r}" for q in queries))
        print(f"dry-run: no requests sent ({len(fetch_keys)} to fetch + "
              f"{len(fresh_keys)} cached; up to {len(fetch_keys) * 3} calls planned).")
        return 0

    # --- cards already fresh: emit a cache snapshot, spend no API calls ----
    for key in fresh_keys:
        cached = latest[key]
        for record in unique[key]:
            carry_forward(record, cached)
            record["served_from"] = "cache"
            append_jsonl(SNAPSHOT_JSONL, record)

    client = PokeWalletClient(verbose=False)
    calls = 0
    cards_found = 0
    stopped = False

    for key in fetch_keys:
        set_id, number_norm = key
        sample = unique[key][0]
        num_padded = numerator(sample["number"]) or number_norm
        api_name = sample.get("api_set_name") or sample["set"]
        # Query keys, most precise first. ``set_id`` is exact for positive ids
        # (the docs' method); ``set_code`` and the canonical set *name* cover
        # the sets whose id is negative (e.g. LOT = -113) where the id query
        # returns unrelated cards. Every candidate is validated before use.
        queries = list(dict.fromkeys([
            f"{set_id} {num_padded}",
            f"{sample['set_code']} {num_padded}",
            f"{api_name} {num_padded}",
        ]))

        card: dict | None = None
        used_query = queries[0]
        pick = "none"
        candidate = ""
        for query in queries:
            if args.max_calls and calls >= args.max_calls:
                print(f"max-calls cap ({args.max_calls}) reached; stopping.", file=sys.stderr)
                stopped = True
                break
            try:
                resp = client.search(q=query, limit=5, force=args.force)
            except BudgetExhausted as exc:
                print(f"budget guard: {exc}", file=sys.stderr)
                stopped = True
                break
            except MissingApiKey as exc:
                print(f"missing key: {exc}", file=sys.stderr)
                return 2
            calls += 1
            used_query = query
            if not resp.ok:
                print(f"  HTTP {resp.status} for q={query!r} "
                      f"({resp.api_error or resp.error})", file=sys.stderr)
                continue
            results = search_results(resp.data)
            card, pick = pick_card(
                results, number_norm, sample["product_name"], set_id,
                sample["set_code"],
            )
            if card is not None:
                break
            if results and not candidate:
                candidate = candidate_summary(results[0])
        if stopped:
            break

        cached = latest.get(key)
        for record in unique[key]:
            record["query"] = used_query
            record["match_method"] = f"set:{record['set_match']}+card:{pick}"
            record["candidate"] = candidate
            if card is not None:
                record.update(pricelib.card_identity(card))
                record.update(pricelib.extract_prices(card))
                record["found"] = True
                record["served_from"] = "fetched"
            else:
                # A failed lookup must never erase a previously-known price.
                had_cache = carry_forward(record, cached)
                record["served_from"] = "cache-fallback" if had_cache else "miss"
            append_jsonl(SNAPSHOT_JSONL, record)
        if card is not None:
            cards_found += 1

    # --- orphan rows still get a (price-less) snapshot so nothing is lost ---
    for record in orphan_rows:
        record["served_from"] = "orphan"
        append_jsonl(SNAPSHOT_JSONL, record)

    # --- flat csv for the sheet -------------------------------------------
    snapshot_csv = unique_path(config.SNAPSHOTS_DIR / f"snapshot_{run_id}.csv")
    ensure_dir(snapshot_csv.parent)
    wrote = 0
    with snapshot_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(SNAPSHOT_HEADER)
        for key in all_keys:
            for record in unique[key]:
                writer.writerow([record.get(col, "") for col in SNAPSHOT_HEADER])
                wrote += 1
        for record in orphan_rows:
            writer.writerow([record.get(col, "") for col in SNAPSHOT_HEADER])
            wrote += 1

    print(f"fetched fresh:          {cards_found} / {len(fetch_keys)}")
    print(f"served from cache:      {len(fresh_keys)}")
    print(f"api calls this run:     {calls}")
    print(client.budget_status())
    if stopped:
        print("NOTE: run stopped early (budget/cap). Re-run later to continue — "
              "snapshots are append-only and safe to repeat.")
    print(f"appended jsonl:         {SNAPSHOT_JSONL}  (+{wrote - len(orphan_rows)} rows)")
    print(f"snapshot csv:           {snapshot_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
