#!/usr/bin/env python3
"""Derive the analysis fields from the 82 scraped FINN ads.

Stdlib only: this reads JSON that is already on disk and does regex work. A
third-party package would add nothing.

Reads
  data/photos-receives-2026-11-08-224643/targets.jsonl   (run attribution, rank)
  data/finn/annonser/{kode}_*/{kode}.json                (the scraped ad views)

Writes
  data/photos-receives-2026-11-08-224643/ads_extract.json

Prints a full table plus the statistics the report is built from.
"""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANNONSER = HERE.parent / "finn" / "annonser"
TARGETS = HERE / "targets.jsonl"
OUT = HERE / "ads_extract.json"

# ---------------------------------------------------------------- vocab -----
JP = ("japansk", "japan", "jap.", " jap", "jpn", "日本語", "japanese")
SEALED = ("sealed", "forseglet", "uåpnet", "uopnet", "ubrut", "uåpna", "fabrikkforseglet")
BOX = ("booster box", "boosterbox", "booster boks", "display box", "display", "boks", "booster")
ETB = ("elite trainer", "etb")
BUNDLE = ("bundle",)
PACK = ("pack", "pakke", "pakker")
TIN = ("tin", "mini tin")
COLLECTION = ("golden box", "upc", "premium collection", "figure collection",
              "collection box", "kolleksjon", "akryl", "acrylic", "case")
SINGLE = ("psa", "cgc", "bgs", "graded", "holo", " sar", "sar ", "#", "/1", "single")
CN = ("kinesisk", "chinese", "151c", "gathering", "crystal gathering", "slim")
KR = ("koreansk", "korean")
NOT_POKEMON = ("one piece", "yu-gi-oh", "yugioh", "lorcana", "digimon",
               "dragon ball", "magic the gathering", "mtg")

# alias -> canonical offer set name
ALIASES: dict[str, str] = {
    "snow hazard": "Snow Hazard",
    "violet ex": "Violet ex",
    "vstar universe": "VSTAR Universe",
    "paradigm trigger": "Paradigm Trigger",
    "lost abyss": "Lost Abyss",
    "battle region": "Battle Region",
    "vmax climax": "VMAX Climax",
    "25th anniversary": "25th Anniversary Collection",
    "25th celebrations": "25th Anniversary Collection",
    "celebrations": "25th Anniversary Collection",
    "eevee heroes": "Eevee Heroes",
    "jet-black spirit": "Jet-Black Spirit",
    "jet black spirit": "Jet-Black Spirit",
    "silver lance": "Silver Lance",
    "30th celebration": "30th CELEBRATION",
    "30 år": "30th CELEBRATION",
    "storm emerald": "Storm Emerald",
    "storm emeralda": "Storm Emerald",
    "abyss eye": "Abyss Eye",
    "ninja spinner": "Ninja Spinner",
    "munikis zero": "Munikis Zero",
    "nihil zero": "Munikis Zero",
    "mega dream": "Mega Dream ex",
    "inferno x": "Inferno X",
    "mega brave": "Mega Brave",
    "mega symphonia": "Mega Symphonia",
    "black bolt": "Black Bolt",
    "white flare": "White Flare",
    "heat wave arena": "Heat Wave Arena",
    "battle partners": "Battle Partners",
    "terastal festival": "Terastal Festival ex",
    "stellar miracle": "Stellar Miracle",
    "night wanderer": "Night Wanderer",
    "mask of change": "Mask of Change",
    "shiny treasure": "Shiny Treasure ex",
    "ancient roar": "Ancient Roar",
    "future flash": "Future Flash",
    "ruler of the black flame": "Ruler of the Black Flame",
    "raging surf": "Raging Surf",
    "clay burst": "Clay Burst",
    "151": "Pokémon Card 151",
    # sets that are NOT in the offer but showed up on FINN
    "crimson haze": "Crimson Haze",
    "incandescent arcana": "Incandescent Arcana",
    "shiny star v": "Shiny Star V",
    "super electric breaker": "Super Electric Breaker",
    "pokemon go": "Pokémon GO",
    "prismatic evolutions": "Prismatic Evolutions",
    "delta reign": "Delta Reign",
    "phantasmal flames": "Phantasmal Flames",
    "chaos rising": "Chaos Rising",
    "journey together": "Journey Together",
    "surging sparks": "Surging Sparks",
    "evolving skies": "Evolving Skies",
    "paldea evolved": "Paldea Evolved",
    "chilling reign": "Chilling Reign",
    "silver tempest": "Silver Tempest",
    "fusion strike": "Fusion Strike",
    "champion path": "Champion Path",
    "ascended heroes": "Ascended Heroes",
    "shining fates": "Shining Fates",
    "crown zenith": "Crown Zenith",
    "paldean fates": "Paldean Fates",
    "destined rivals": "Destined Rivals",
    "perfect order": "Perfect Order",
    "pitch black": "Pitch Black",
    "phantasmal": "Phantasmal Flames",
}

OFFER_SETS = {
    "Snow Hazard", "Violet ex", "VSTAR Universe", "Paradigm Trigger", "Lost Abyss",
    "Battle Region", "VMAX Climax", "25th Anniversary Collection", "Eevee Heroes",
    "Jet-Black Spirit", "Silver Lance", "30th CELEBRATION", "Storm Emerald",
    "Abyss Eye", "Ninja Spinner", "Munikis Zero", "Mega Dream ex", "Inferno X",
    "Mega Brave", "Mega Symphonia", "Black Bolt", "White Flare", "Heat Wave Arena",
    "Battle Partners", "Terastal Festival ex", "Stellar Miracle", "Night Wanderer",
    "Mask of Change", "Shiny Treasure ex", "Ancient Roar", "Future Flash",
    "Ruler of the Black Flame", "Raging Surf", "Clay Burst", "Pokémon Card 151",
}

# Only *boxes* count as a lot. "30 pakker" is 30 packs inside one box, and
# "14x V / VSTAR / AR" is a pile of singles -- neither is a multi-box lot.
_RE_LOT = re.compile(r"(?:^|\s)(\d{1,3})\s*(?:x\s+)?(?:bokser|boxes|booster\s*box(?:er)?|display)\b", re.I)
_RE_LOT2 = re.compile(r"\b(\d{1,3})\s?x\s+(?:booster\s*box|boks|box)\b", re.I)
_RE_PER_BOX = re.compile(r"per\s+(?:boks|box|stk)", re.I)


def has(h: str, words: tuple[str, ...]) -> bool:
    return any(w in h for w in words)


def detect_set(text: str) -> str | None:
    t = text.lower()
    best: tuple[int, str] | None = None
    for alias, canon in ALIASES.items():
        if alias in t:
            # prefer the longest alias match ("mega dream" over "dream")
            if best is None or len(alias) > best[0]:
                best = (len(alias), canon)
    return best[1] if best else None


def detect_language(h: str, desc: str) -> str:
    """Language from the heading, falling back to the *opening* of the description.

    The full description is useless for this: sellers stuff 2 000 characters of
    SEO tags at the bottom, and those tags always include "Japansk Pokemon" and
    "Japanese Pokemon" even on English product. That is how an English Paldea
    Evolved box gets labelled Japanese. Only the first 300 characters are prose.
    """
    t = (h + " " + desc[:300]).lower()
    if has(t, CN):
        return "CN"
    if has(t, KR):
        return "KR"
    if has(t, JP):
        return "JP"
    return "EN/unknown"


def detect_product(h: str) -> str:
    t = h.lower()
    if has(t, SINGLE):
        return "single/graded"
    if has(t, ETB):
        return "ETB"
    if has(t, TIN):
        return "tin"
    if has(t, COLLECTION):
        return "collection box"
    if has(t, BUNDLE):
        return "bundle"
    if has(t, PACK):
        return "pack"
    if has(t, BOX):
        return "booster box"
    return "other"


# A lot bigger than this is not a lot, it is a set number ("151 Booster Box")
# or a pack count that slipped through. Reject rather than divide by it.
MAX_LOT = 30


def boxes_in_lot(h: str, desc: str) -> int:
    for text in (h, desc[:400]):
        for rx in (_RE_LOT, _RE_LOT2):
            m = rx.search(text)
            if m:
                n = int(m.group(1))
                if 1 <= n <= MAX_LOT:
                    return n
    return 1


def main() -> int:
    targets = [json.loads(l) for l in TARGETS.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_kode: dict[str, list[dict]] = {}
    for t in targets:
        by_kode.setdefault(t["finn_kode"], []).append(t)

    records: list[dict] = []
    missing: list[str] = []

    for kode, hits in sorted(by_kode.items()):
        folders = list(ANNONSER.glob(f"{kode}_*"))
        if not folders:
            missing.append(kode)
            continue
        f = folders[0] / f"{kode}.json"
        if not f.exists():
            missing.append(kode)
            continue
        ad = json.loads(f.read_text(encoding="utf-8"))

        heading = ad.get("title") or ""
        desc = ad.get("description_raw") or ""
        price = ad.get("price_nok")
        product = detect_product(heading)
        # A lot size only means anything for a booster box. For a pack, a
        # bundle or a singles pile, "per box" is a meaningless number.
        lot = boxes_in_lot(heading, desc) if product == "booster box" else 1
        lang = detect_language(heading, desc)
        canon = detect_set(heading) or detect_set(desc[:300])
        segment = (ad.get("contact_button") or {}).get("segment") or "UNKNOWN"
        other_tcg = has((heading + " " + desc[:200]).lower(), NOT_POKEMON)
        # One ad is not a single set: it is a reseller's whole price list.
        price_list = desc.count("Booster Box kr") >= 5
        if price_list:
            canon = "MULTI (price list)"

        records.append({
            "finn_kode": kode,
            "title": heading,
            "price_nok": price,
            "status": ad.get("status"),
            "trade_type": ad.get("trade_type"),
            "condition": ad.get("condition"),
            "item_condition": (ad.get("ld_json") or {}).get("item_condition"),
            "location": ad.get("location_text"),
            "last_modified": ad.get("last_modified"),
            "gallery_count": ad.get("gallery_count"),
            "seller_segment": segment,
            "language": lang,
            "product": product,
            "boxes_in_lot": lot,
            "price_per_box": (None if (price is None or product != "booster box")
                              else round(price / lot)),
            "set": canon,
            "set_in_offer": canon in OFFER_SETS if canon else False,
            "other_tcg": other_tcg,
            "price_list": price_list,
            "desc_len": len(desc),
            "desc": desc,
            "similar_count": len(ad.get("similar_ads") or []),
            "runs": sorted({h["run_id"] for h in hits}),
            "best_rank": min(h["rank"] for h in hits),
            "best_score": max(h["score"] for h in hits),
            "url": f"https://www.finn.no/recommerce/forsale/item/{kode}",
        })

    OUT.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"targets rows      : {len(targets)}")
    print(f"unique koder      : {len(by_kode)}")
    print(f"records built     : {len(records)}")
    print(f"missing           : {len(missing)}  {missing if missing else ''}")

    # ---- the real comparable set: JP + sealed + booster box -----------------
    core = [r for r in records
            if r["language"] == "JP" and r["product"] == "booster box"
            and not r["other_tcg"]
            and r["price_nok"] and r["price_nok"] >= 100]
    print(f"\nJP sealed booster boxes among the 82 : {len(core)}")
    prices = sorted(r["price_per_box"] for r in core)
    if prices:
        print(f"  min {prices[0]:,}  median {statistics.median(prices):,.0f}  max {prices[-1]:,}")

    print("\n--- by product type ---")
    for p in sorted({r["product"] for r in records}):
        n = sum(1 for r in records if r["product"] == p)
        print(f"  {p:<16} {n:>3}")

    print("\n--- by language ---")
    for l in sorted({r["language"] for r in records}):
        n = sum(1 for r in records if r["language"] == l)
        print(f"  {l:<12} {n:>3}")

    print("\n--- by seller segment ---")
    for s in sorted({r["seller_segment"] for r in records}):
        n = sum(1 for r in records if r["seller_segment"] == s)
        print(f"  {s:<14} {n:>3}")

    print("\n--- by set (offer sets only) ---")
    for s in sorted({r["set"] for r in records if r["set_in_offer"]}):
        rows = [r for r in records if r["set"] == s]
        ps = sorted(r["price_per_box"] for r in rows if r["price_per_box"])
        if ps:
            print(f"  {s:<28} ads={len(rows):<2} boxes={len(ps):<2} "
                  f"min={ps[0]:>6,} med={statistics.median(ps):>7,.0f} max={ps[-1]:>6,}")
        else:
            print(f"  {s:<28} ads={len(rows):<2} boxes=0   (no booster box with a price)")

    print("\n--- full table ---")
    print(f"{'kode':<10}{'NOK':>7}{'lot':>4}{'NOK/box':>9}  {'lang':<4}{'product':<15}{'seller':<12}{'set':<26}title")
    for r in sorted(records, key=lambda r: (r["set"] or "zzz", -(r["price_per_box"] or 0))):
        print(f"{r['finn_kode']:<10}{r['price_nok'] or 0:>7,}{r['boxes_in_lot']:>4}"
              f"{r['price_per_box'] or 0:>9,}  {r['language']:<4}{r['product']:<15}"
              f"{r['seller_segment']:<12}{(r['set'] or '-')[:25]:<26}{r['title'][:60]}")

    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
