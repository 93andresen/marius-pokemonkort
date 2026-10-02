#!/usr/bin/env python3
"""resolve_portfolio.py — map the Collectr export onto PokeWallet cards.

Two phases:

* **Offline (default):** parse the CSV, match each row's set against the cached
  set index, normalise card numbers, and write a resolved CSV plus an
  unmatched-sets report. No API calls.
* **``--fetch``:** additionally fetch each matched set once (``GET /sets/:code``)
  to resolve the concrete card id and current prices. Rate-aware, cached
  (a set is only fetched once unless ``--refetch``), and resumable.

    uv run pokewallet/resolve_portfolio.py
    uv run pokewallet/resolve_portfolio.py --fetch
    uv run pokewallet/resolve_portfolio.py --fetch --limit 10
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from pwlib import config, portfolio, prices as pricelib, sets as setslib
from pwlib.api import BudgetExhausted, MissingApiKey, PokeWalletClient
from pwlib.util import now_ts, slugify, write_json, write_text

RESOLVED_HEADER = [
    "row_index", "portfolio", "category", "set", "product_name", "card_number",
    "number_norm", "rarity", "variance", "grade", "condition", "quantity",
    "avg_cost_paid_nok", "collectr_market_nok", "watchlist", "date_added",
    "set_id", "set_code", "set_language", "set_match",
    "pk_id", "pk_name", "pk_set_name", "pk_set_code", "pk_card_number", "pk_rarity",
    "match_method", "match_confidence",
    "tcg_market", "tcg_low", "tcg_mid", "tcg_high", "tcg_subtype", "tcg_updated",
    "tcgplayer_url",
    "cmk_trend", "cmk_avg", "cmk_low", "cmk_variant",
    "price_source", "notes",
]

_SET_CONFIDENCE = {"code": 1.0, "name_exact": 0.95, "name_prefix": 0.7, "none": 0.0}


# --- index -----------------------------------------------------------------
def latest_index_file() -> Path | None:
    files = sorted(config.SETS_DIR.glob("set_index_*.json"))
    return files[-1] if files else None


def load_index() -> dict:
    path = latest_index_file()
    if path is None:
        raise SystemExit(
            "no set index found — run `uv run pokewallet/sync_sets.py` first."
        )
    print(f"using set index: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))["index"]


# --- set-card fetching -----------------------------------------------------
def locate_cards(payload: object) -> list[dict] | None:
    """Find the list of card dicts inside a ``/sets/:code`` response."""
    if isinstance(payload, list):
        return [c for c in payload if isinstance(c, dict)]
    if isinstance(payload, dict):
        for key in ("cards", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [c for c in value if isinstance(c, dict)]
            if isinstance(value, dict):
                for sub in ("cards", "results"):
                    if isinstance(value.get(sub), list):
                        return [c for c in value[sub] if isinstance(c, dict)]
    return None


def cached_cards_file(set_code: str) -> Path | None:
    files = sorted(config.SETS_DIR.glob(f"cards_{slugify(set_code)}_*.json"))
    return files[-1] if files else None


def load_cards(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("cards", []) if isinstance(data, dict) else data


def fetch_set_cards(
    client: PokeWalletClient, set_code: str, refetch: bool
) -> tuple[list[dict] | None, str]:
    if not refetch:
        cached = cached_cards_file(set_code)
        if cached is not None:
            return load_cards(cached), f"cache:{cached.name}"
    resp = client.set(set_code)
    if not resp.ok:
        return None, f"http:{resp.status}"
    cards = locate_cards(resp.data)
    if cards is None:
        return None, "unrecognised_payload"
    write_json(
        config.SETS_DIR / f"cards_{slugify(set_code)}_{now_ts()}.json",
        {"set_code": set_code, "fetched_at": now_ts(), "cards": cards},
    )
    return cards, "fetched"


def build_number_map(cards: list[dict]) -> dict[str, dict]:
    """Map every number variant of each card to the card object."""
    mapping: dict[str, dict] = {}
    for card in cards:
        info = card.get("card_info") or card
        number = info.get("card_number")
        for variant in portfolio.number_variants(number):
            mapping.setdefault(variant, card)
    return mapping


# --- main ------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=str(config.COLLECTR_CSV),
                        help="path to the Collectr export CSV")
    parser.add_argument("--fetch", action="store_true",
                        help="fetch sets to resolve card ids + prices (uses requests)")
    parser.add_argument("--refetch", action="store_true",
                        help="with --fetch, ignore cached set-card files")
    parser.add_argument("--limit", type=int, default=None,
                        help="only process the first N rows (testing)")
    parser.add_argument("--force", action="store_true",
                        help="ignore the rate-budget safety floor")
    args = parser.parse_args(argv)

    fieldnames, rows = portfolio.read_rows(args.csv)
    if args.limit:
        rows = rows[: args.limit]
    market_col = portfolio.market_column(fieldnames)
    index = load_index()

    results: list[dict] = []
    unmatched_sets: dict[str, int] = {}
    matched_by_set_code: dict[str, list[dict]] = {}

    for i, row in enumerate(rows, start=1):
        set_name = (row.get(portfolio.SET_COL) or "").strip()
        number_raw = row.get(portfolio.NUMBER_COL)
        entry, set_method = setslib.lookup(index, set_name)

        set_id = entry.get("set_id") if entry else ""
        set_code = entry.get("set_code") if entry else ""
        set_language = entry.get("language") if entry else ""

        if not entry:
            unmatched_sets[set_name] = unmatched_sets.get(set_name, 0) + 1

        record = {
            "row_index": i,
            "portfolio": row.get(portfolio.PORTFOLIO_COL, ""),
            "category": row.get(portfolio.CATEGORY_COL, ""),
            "set": set_name,
            "product_name": row.get(portfolio.NAME_COL, ""),
            "card_number": number_raw,
            "number_norm": portfolio.number_norm(number_raw),
            "rarity": row.get(portfolio.RARITY_COL, ""),
            "variance": row.get(portfolio.VARIANCE_COL, ""),
            "grade": row.get(portfolio.GRADE_COL, ""),
            "condition": row.get(portfolio.CONDITION_COL, ""),
            "quantity": portfolio.parse_quantity(row.get(portfolio.QTY_COL)),
            "avg_cost_paid_nok": portfolio.parse_money(row.get(portfolio.COST_COL)),
            "collectr_market_nok": portfolio.parse_money(row.get(market_col)) if market_col else None,
            "watchlist": row.get(portfolio.WATCHLIST_COL, ""),
            "date_added": row.get(portfolio.DATE_ADDED_COL, ""),
            "set_id": set_id,
            "set_code": set_code,
            "set_language": set_language,
            "set_match": set_method,
            "match_method": f"set:{set_method}",
            "match_confidence": _SET_CONFIDENCE.get(set_method, 0.0),
            "notes": row.get(portfolio.NOTES_COL, ""),
        }
        results.append(record)
        if entry and set_code:
            matched_by_set_code.setdefault(set_code, []).append(record)

    # --- report (offline) --------------------------------------------------
    print(f"rows: {len(results)}")
    print(f"distinct sets: {len(portfolio.distinct_sets(rows))}")
    print(f"rows with a matched set: {sum(1 for r in results if r['set_match'] != 'none')}")
    if unmatched_sets:
        print(f"unmatched sets ({len(unmatched_sets)}):")
        for name, count in sorted(unmatched_sets.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {count:>3}× {name!r}")

    ts = now_ts()

    # --- optional fetch phase ---------------------------------------------
    if args.fetch:
        client = PokeWalletClient()
        fetched = 0
        failed: list[tuple[str, str]] = []
        for set_code in sorted(matched_by_set_code):
            try:
                cards, status = fetch_set_cards(client, set_code, args.refetch)
            except BudgetExhausted as exc:
                print(f"budget guard: {exc}", file=sys.stderr)
                break
            except MissingApiKey as exc:
                print(f"missing key: {exc}", file=sys.stderr)
                return 2
            if cards is None:
                failed.append((set_code, status))
                continue
            number_map = build_number_map(cards)
            for record in matched_by_set_code[set_code]:
                num_key = record["number_norm"]
                card = number_map.get(num_key)
                if card is None:
                    for variant in portfolio.number_variants(record["card_number"]):
                        if variant in number_map:
                            card = number_map[variant]
                            break
                if card is None:
                    record["match_method"] += "+card:none"
                    continue
                record.update(pricelib.card_identity(card))
                record.update(pricelib.extract_prices(card))
                record["match_method"] += "+card:number"
                record["match_confidence"] = min(1.0, record["match_confidence"] + 0.05)
                fetched += 1
        print(f"cards resolved via API: {fetched} / {sum(len(v) for v in matched_by_set_code.values())}")
        if failed:
            print(f"set fetches failed ({len(failed)}):", file=sys.stderr)
            for code, status in failed:
                print(f"  {code}: {status}", file=sys.stderr)

    # --- write outputs -----------------------------------------------------
    out_dir = config.POKEWALLET_DATA
    csv_path = out_dir / f"resolved_portfolio_{ts}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(RESOLVED_HEADER)
        for record in results:
            writer.writerow([record.get(col, "") for col in RESOLVED_HEADER])

    report_lines = [f"generated_at: {ts}", f"rows: {len(results)}", ""]
    report_lines += [
        f"{count}\t{name}" for name, count in sorted(unmatched_sets.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    report_path = write_text(
        out_dir / f"unmatched_sets_{ts}.txt",
        "\n".join(report_lines) + "\n",
    )

    print(f"resolved csv:     {csv_path}")
    print(f"unmatched report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
