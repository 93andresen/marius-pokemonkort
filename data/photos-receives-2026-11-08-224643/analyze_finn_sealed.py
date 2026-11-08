#!/usr/bin/env python3
"""Summarise today's FINN search runs for Japanese sealed booster boxes.

Reads every ``all_ads.jsonl`` under ``data/finn/searches/2026-11-08-22*/``,
dedupes by FINN-kode, and buckets headings by language / sealed / box signals
so we can see what is actually on the market before scraping anything.

Stdlib only: read-only aggregation over local JSONL files.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEARCHES = ROOT / "data" / "finn" / "searches"

JP = ("japansk", "japan", "jap.", " jap", "日本語", "jpn")
SEALED = ("sealed", "forseglet", "uåpnet", "uopnet", "ubrut", "uåpna", "uåpnet")
BOX = ("booster box", "boosterbox", "display box", "display", "box", "boks", "booster")
POKEMON = ("pokemon", "pokémon", "poké")
NOT_POKEMON = ("one piece", "yu-gi-oh", "yugioh", "lorcana", "digimon",
               "dragon ball", "magic the gathering", "mtg", "sports")
LOT = ("x2", "x 2", "x3", "x 3", "stk", " lot", "samling", "flere", "pakker")


def load() -> dict[str, dict]:
    ads: dict[str, dict] = {}
    files = sorted(SEARCHES.glob("2026-11-08-22*/all_ads.jsonl"))
    print(f"reading {len(files)} run(s)")
    for path in files:
        n = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            kode = rec.get("finn_kode")
            if not kode:
                continue
            n += 1
            if kode not in ads:
                rec["_queries"] = [rec.get("query")]
                ads[kode] = rec
            else:
                q = rec.get("query")
                if q and q not in ads[kode]["_queries"]:
                    ads[kode]["_queries"].append(q)
        print(f"  {path.parent.name}: {n} rows")
    return ads


def flags(heading: str) -> tuple[bool, bool, bool, bool]:
    h = (heading or "").lower()
    # The category is already restricted to Samlekort and every query says
    # "pokemon", so non-Pokemon TCGs are the exception -- exclude them rather
    # than requiring the word "Pokemon" (many Japanese set names omit it).
    is_pokemon = not any(k in h for k in NOT_POKEMON)
    return (
        is_pokemon,
        any(k in h for k in JP),
        any(k in h for k in SEALED),
        any(k in h for k in BOX),
    )


def is_lot(heading: str) -> bool:
    h = (heading or "").lower()
    return any(k in h for k in LOT)


def money(rec: dict) -> str:
    amt = rec.get("price_amount")
    cur = rec.get("price_currency") or ""
    if amt is None:
        return "—"
    return f"{amt:,}".replace(",", " ") + f" {cur}".rstrip()


def show(title: str, rows: list[dict]) -> None:
    print(f"\n### {title}  ({len(rows)})")
    if not rows:
        print("  (none)")
        return
    rows = sorted(rows, key=lambda r: (r.get("price_amount") is None, r.get("price_amount") or 0))
    for r in rows:
        lot = " [LOT?]" if is_lot(r.get("heading") or "") else ""
        print(f"  {r['finn_kode']:<12} {money(r):>12}  {(r.get('heading') or '')[:78]}{lot}")
        print(f"  {'':<12} {'':>12}  queries={r['_queries']}")


def main() -> None:
    ads = load()
    print(f"\nunique ads across all runs: {len(ads)}")

    buckets: dict[str, list[dict]] = {"jp_box": [], "sealed_box": [], "box_only": [], "jp_only": []}
    for rec in ads.values():
        is_pokemon, has_jp, has_sealed, has_box = flags(rec.get("heading") or "")
        if not is_pokemon:
            continue
        if has_jp and has_box:
            buckets["jp_box"].append(rec)
        elif has_sealed and has_box:
            buckets["sealed_box"].append(rec)
        elif has_box:
            buckets["box_only"].append(rec)
        elif has_jp:
            buckets["jp_only"].append(rec)

    show("A. Japanese + box/booster/display", buckets["jp_box"])
    show("B. Sealed + box/booster/display (language unstated)", buckets["sealed_box"])
    show("C. Box/booster/display only (language unstated)", buckets["box_only"])
    show("D. Japanese only (no box signal)", buckets["jp_only"])

    priced = [r["price_amount"] for r in buckets["jp_box"] + buckets["sealed_box"]
              if r.get("price_amount")]
    print(f"\n### price stats for A+B ({len(priced)} priced ads)")
    if priced:
        print(f"  min    : {min(priced):,}".replace(",", " "))
        print(f"  median : {statistics.median(priced):,.0f}".replace(",", " "))
        print(f"  max    : {max(priced):,}".replace(",", " "))


if __name__ == "__main__":
    main()
