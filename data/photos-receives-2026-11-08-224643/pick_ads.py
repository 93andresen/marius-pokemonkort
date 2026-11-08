#!/usr/bin/env python3
"""Pick the 10 most relevant ads from each of the 13 FINN search runs.

Stdlib only -- this is a scoring pass over JSONL that is already on disk, so
there is nothing a third-party package would do better.

Relevance is scored against what we actually care about: a *Japanese, sealed,
booster box* of a set that appears in the wholesale offer. Everything else
(English product, ETBs, single packs, graded singles, other TCGs) is pushed
down, and placeholder 1-NOK listings are pushed down hard.

Output: ``targets.jsonl`` -- one line per selected ad, carrying the run it came
from, its rank within that run, the score, and the fields ``finn_ad.py`` needs.
The same file can be fed straight to ``finn_ad.py --from-jsonl`` (it dedupes).
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEARCHES = HERE.parent / "finn" / "searches"
OUT = HERE / "targets.jsonl"
PER_SEARCH = 10

JP = ("japansk", "japan", "jap.", " jap", "jpn", "日本語")
SEALED = ("sealed", "forseglet", "uåpnet", "uopnet", "ubrut", "uåpna", "fabrikkforseglet")
BOX = ("booster box", "boosterbox", "booster boks", "display box", "display", "boks", "booster")
POKEMON = ("pokemon", "pokémon", "poké")
NOT_POKEMON = ("one piece", "yu-gi-oh", "yugioh", "lorcana", "digimon",
               "dragon ball", "magic the gathering", "mtg", "sports")
SINGLE = ("psa", "cgc", "bgs", "graded", "holo", " sar", "sar ", "#", "/1", "single")
NOT_BOX = ("elite trainer", "etb", "bundle", "tin", "pack", "pakke", "sleeve",
           "album", "akryl", "acrylic", "case", "blindboks", "mini tin")

# Set names from the offer, plus the spellings FINN actually uses.
SETS = (
    "snow hazard", "violet ex", "vstar universe", "paradigm trigger", "lost abyss",
    "battle region", "vmax climax", "25th anniversary", "eevee heroes",
    "jet-black spirit", "jet black spirit", "silver lance", "30th celebration",
    "storm emerald", "storm emeralda", "abyss eye", "ninja spinner",
    "munikis zero", "nihil zero", "mega dream", "inferno x", "mega brave",
    "mega symphonia", "black bolt", "white flare", "heat wave arena",
    "battle partners", "terastal festival", "stellar miracle", "night wanderer",
    "mask of change", "shiny treasure", "ancient roar", "future flash",
    "ruler of the black flame", "raging surf", "clay burst", "151",
    "crimson haze", "incandescent arcana", "shiny star v", "super electric breaker",
    "pokemon go", "prismatic evolutions", "delta reign", "phantasmal flames",
)


def score(ad: dict) -> tuple[int, list[str]]:
    h = (ad.get("heading") or "").lower()
    price = ad.get("price_amount")
    s = 0
    why: list[str] = []

    if any(k in h for k in NOT_POKEMON):
        s -= 300
        why.append("-300 other TCG")
    if any(k in h for k in JP):
        s += 100
        why.append("+100 japanese")
    if any(k in h for k in SEALED):
        s += 60
        why.append("+60 sealed")
    if any(k in h for k in BOX):
        s += 50
        why.append("+50 box")
    if any(k in h for k in POKEMON):
        s += 20
        why.append("+20 pokemon")
    hit = [n for n in SETS if n in h]
    if hit:
        s += 40
        why.append(f"+40 offer set ({hit[0]})")
    if any(k in h for k in SINGLE):
        s -= 80
        why.append("-80 single/graded")
    if any(k in h for k in NOT_BOX):
        s -= 60
        why.append("-60 not a box")
    if price is None:
        s -= 200
        why.append("-200 no price")
    elif price < 100:
        s -= 200
        why.append("-200 placeholder price")
    elif price > 20_000:
        s -= 20
        why.append("-20 lot / high price")
    return s, why


def main() -> int:
    runs = sorted(p for p in SEARCHES.iterdir() if p.is_dir() and p.name.startswith("2026-11-08-22"))
    if not runs:
        print("FATAL: no 2026-11-08-22* run folders found")
        return 1

    selected: list[dict] = []
    seen: dict[str, list[str]] = {}

    for run in runs:
        f = run / "all_ads.jsonl"
        if not f.exists():
            print(f"WARN: {run.name} has no all_ads.jsonl -- skipped")
            continue
        ads = [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
        scored = []
        for ad in ads:
            s, why = score(ad)
            scored.append((s, ad, why))
        # highest score first; tie-break on price descending (bigger ticket = more relevant)
        scored.sort(key=lambda t: (-t[0], -(t[1].get("price_amount") or 0)))

        query = ads[0].get("query", "?") if ads else "?"
        print(f"\n=== {run.name}  query={query!r}  ads={len(ads)}")
        for rank, (s, ad, why) in enumerate(scored[:PER_SEARCH], start=1):
            kode = ad["finn_kode"]
            seen.setdefault(kode, []).append(run.name)
            selected.append({
                "run_id": run.name,
                "query": query,
                "rank": rank,
                "score": s,
                "why": why,
                "finn_kode": kode,
                "heading": ad.get("heading"),
                "price_amount": ad.get("price_amount"),
                "location": ad.get("location"),
                "canonical_url": ad.get("canonical_url"),
            })
            print(f"  {rank:>2}. {s:>5}  {kode}  {ad.get('price_amount')!s:>7}  {ad.get('heading')}")

    OUT.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in selected) + "\n",
        encoding="utf-8",
    )

    unique = sorted(seen)
    multi = {k: v for k, v in seen.items() if len(v) > 1}
    print(f"\nselected rows      : {len(selected)}  ({len(runs)} runs x {PER_SEARCH})")
    print(f"unique FINN-koder  : {len(unique)}")
    print(f"appearing in >1 run: {len(multi)}")
    for k, v in sorted(multi.items()):
        print(f"  {k}  in {len(v)} runs: {', '.join(v)}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
