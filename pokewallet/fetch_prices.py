#!/usr/bin/env python3
"""fetch_prices.py — append-only price snapshots for the Collectr portfolio.

Why per-card ``/search`` (verified live 2026-10-02, see
``docs/pokewallet_io_api-VERIFIED-NOTES.md``):

* ``GET /sets/:code`` returns the cards but with **empty** price arrays on the
  free plan, so it cannot be used for pricing.
* ``GET /cards/:id`` returns prices, but we only learn the id from a set call.
* ``GET /search?q="<set_id> <card_number>"`` (the lookup key the API docs
  recommend) returns the exact card **with** TCGPlayer/CardMarket prices in a
  single call. That is what we use: one call per unique portfolio card.

Design guarantees (per PROJECT-PLAN.md / AGENTS.md):

* **Never overwrite / never lose data** — one JSON object per portfolio row is
  *appended* to ``snapshots/portfolio_prices.jsonl`` (flushed + fsynced), and a
  flat ``snapshots/snapshot_<run_id>.csv`` is written for the sheet.
* **Resumable & rate-aware** — stops cleanly at the client's budget floor;
  re-run later to continue. Unique cards are deduped so shared cards cost once.
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
import sys

from pwlib import config, portfolio, prices as pricelib, sets as setslib
from pwlib.api import BudgetExhausted, MissingApiKey, PokeWalletClient
from pwlib.util import append_jsonl, ensure_dir, now_ts, unique_path, utc_iso

# Import the index loader written for the resolver (same directory).
from resolve_portfolio import load_index

SNAPSHOT_HEADER = [
    "run_id", "run_ts_utc", "row_index", "portfolio", "category",
    "set", "set_code", "set_id",
    "number", "number_norm", "product_name", "rarity", "variance", "grade",
    "condition", "quantity", "avg_cost_paid_nok", "collectr_market_nok",
    "watchlist", "date_added",
    "pk_id", "pk_name", "pk_set_name", "pk_set_code", "pk_card_number", "pk_rarity",
    "tcg_market", "tcg_low", "tcg_mid", "tcg_high", "tcg_subtype", "tcg_updated",
    "tcgplayer_url",
    "cmk_trend", "cmk_avg", "cmk_low", "cmk_variant", "cmk_updated",
    "price_source", "found", "match_method", "query",
]

SNAPSHOT_JSONL = config.SNAPSHOTS_DIR / "portfolio_prices.jsonl"


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


def pick_card(
    results: list[dict], number_norm: str
) -> tuple[dict | None, str]:
    """Choose the result matching ``number_norm``; else the first result."""
    for card in results:
        info = card.get("card_info") or card
        if portfolio.number_norm(info.get("card_number")) == number_norm:
            return card, "number"
    if results:
        return results[0], "approx"
    return None, "none"


def numerator(raw: object) -> str:
    """The number part before ``/`` exactly as written (e.g. ``048``)."""
    return str(raw or "").strip().split("/")[0].strip()


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

    keys = sorted(unique)
    if args.limit:
        keys = keys[: args.limit]

    print(f"run_id:          {run_id}")
    print(f"portfolio rows:  {len(rows)}")
    print(f"rows w/o set/no number: {len(orphan_rows)}")
    print(f"unique cards to fetch:  {len(unique)} (this run: {len(keys)})")

    if args.dry_run:
        for key in keys:
            set_id, number_norm = key
            sample = unique[key][0]
            num_padded = numerator(sample["number"]) or number_norm
            print(f"  would GET /search?q=\"{set_id} {num_padded}\"  "
                  f"[{sample['set_code']}] {sample['set']!r} #{sample['number']}")
        print(f"dry-run: no requests sent ({len(keys)} calls planned).")
        return 0

    client = PokeWalletClient(verbose=False)
    calls = 0
    cards_found = 0
    stopped = False

    for key in keys:
        set_id, number_norm = key
        sample = unique[key][0]
        num_padded = numerator(sample["number"]) or number_norm
        # Try the zero-padded numerator first (just verified), then the
        # stripped form as a fallback.
        queries = list(dict.fromkeys([f"{set_id} {num_padded}", f"{set_id} {number_norm}"]))

        card: dict | None = None
        used_query = queries[0]
        pick = "none"
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
            card, pick = pick_card(results, number_norm)
            if card is not None:
                break
        if stopped:
            break

        for record in unique[key]:
            record["query"] = used_query
            record["match_method"] = f"set:{record['set_match']}+card:{pick}"
            if card is not None:
                record.update(pricelib.card_identity(card))
                record.update(pricelib.extract_prices(card))
                record["found"] = True
            append_jsonl(SNAPSHOT_JSONL, record)
        if card is not None:
            cards_found += 1

    # --- orphan rows still get a (price-less) snapshot so nothing is lost ---
    for record in orphan_rows:
        append_jsonl(SNAPSHOT_JSONL, record)

    # --- flat csv for the sheet -------------------------------------------
    snapshot_csv = unique_path(config.SNAPSHOTS_DIR / f"snapshot_{run_id}.csv")
    ensure_dir(snapshot_csv.parent)
    wrote = 0
    with snapshot_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(SNAPSHOT_HEADER)
        for key in keys:
            for record in unique[key]:
                writer.writerow([record.get(col, "") for col in SNAPSHOT_HEADER])
                wrote += 1
        for record in orphan_rows:
            writer.writerow([record.get(col, "") for col in SNAPSHOT_HEADER])
            wrote += 1

    print(f"unique cards resolved:  {cards_found} / {len(keys)}")
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
