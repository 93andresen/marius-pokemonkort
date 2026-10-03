#!/usr/bin/env python3
"""finn_searches.py — the canonical FINN.no search catalog.

This is the machine-readable translation of *what Marius actually searches for*
(see ``prompts-notes/prompts.md``). It is the single, reproducible source of the
search set the whole FINN pipeline is built around:

  * **Broad queries** — the phrases he types ("pokemon kort", "pokemon samling", …).
  * **Set searches** — the specific *sets* he finds interesting, split into
    Tier 1 (the ones he called out first) and Tier 2 ("still interesting, but
    not nearly as much — as long as they are at least 20 years old").
  * **Card searches** — the individual Pokémon he named on the phone.

Every entry is a **search definition**: a query plus the exact FINN search
parameters it should be sent with (so a scrape is never a guess), the sorts to
union, and how many pages to pull. ``finn_search.py`` consumes these via
``--search-set``; ``finn_identify.py`` reuses :data:`SETS` / :data:`CARDS` to
work out *which* interesting thing an ad is.

Nothing here is scraped — it is a hand-curated, version-controlled catalog.
Run ``uv run finn/finn_searches.py --list`` to see it; add ``--json`` for the
exact payload the scraper loads.

CLI
---
  uv run finn/finn_searches.py --list                 # human table
  uv run finn/finn_searches.py --list --tier 1        # only Tier-1 set searches
  uv run finn/finn_searches.py --list --kind set
  uv run finn/finn_searches.py --json                 # full machine catalog
  uv run finn/finn_searches.py --json --kind card
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Iterable

# --- FINN category parameters (verified from the embedded filter map) --------
# https://www.finn.no/recommerce/forsale/search
#   category        0.86        "Fritid, hobby og underholdning"
#   sub_category    1.86.285    "Samleobjekter"
#   product_category 2.86.285.396 "Samlekort"
CARD_PARAMS: dict[str, str] = {
    "category": "0.86",
    "sub_category": "1.86.285",
    "product_category": "2.86.285.396",
}

# Default sorts / page budget. FINN is unioned across sorts (spec §1.5): the
# cheapest insurance against ranking-dependent omissions.
DEFAULT_SORTS = ["PUBLISHED_DESC", "RELEVANCE"]

# --- the interesting SETS (prompts.md lines 108-134) ------------------------
# ``tier`` 1 = "THESE Sets are INTRRESTING"; 2 = "These too, but NOT NEARLY AS
# INTRESTING". ``aliases`` are the strings a seller is likely to put in a FINN
# heading (lower-cased, matched as substrings after normalisation).
SETS: list[dict[str, Any]] = [
    # ---- Tier 1: the WotC-era core -----------------------------------------
    {"name": "Base Set", "year": 1999, "tier": 1,
     "aliases": ["base set", "baseset", "base-set", "base set 1999"]},
    {"name": "Jungle", "year": 1999, "tier": 1, "aliases": ["jungle"]},
    {"name": "Fossil", "year": 1999, "tier": 1, "aliases": ["fossil"]},
    {"name": "Base Set 2", "year": 2000, "tier": 1,
     "aliases": ["base set 2", "baseset 2", "base 2", "base set ii"]},
    {"name": "Team Rocket", "year": 2000, "tier": 1,
     "aliases": ["team rocket", "team-rocket", "rocket set"]},
    {"name": "Gym Heroes", "year": 2000, "tier": 1,
     "aliases": ["gym heroes", "gym hero"]},
    {"name": "Gym Challenge", "year": 2000, "tier": 1,
     "aliases": ["gym challenge"]},
    {"name": "Neo Genesis", "year": 2000, "tier": 1,
     "aliases": ["neo genesis", "neo gen"]},
    {"name": "Neo Discovery", "year": 2001, "tier": 1,
     "aliases": ["neo discovery", "neo disc"]},
    {"name": "Neo Revelation", "year": 2001, "tier": 1,
     "aliases": ["neo revelation", "neo rev"]},
    # ---- Tier 2: still wanted, "as long as they are at least 20 years old" --
    {"name": "Skyridge", "year": 2003, "tier": 2, "aliases": ["skyridge"]},
    {"name": "Base Set (1st Edition / Shadowless)", "year": 1999, "tier": 2,
     "aliases": ["1st edition", "first edition", "1. edition", "shadowless",
                 "shadowless base"]},
    {"name": "Aquapolis", "year": 2003, "tier": 2, "aliases": ["aquapolis"]},
    {"name": "EX Team Rocket Returns", "year": 2004, "tier": 2,
     "aliases": ["team rocket returns", "ex team rocket returns"]},
    {"name": "EX Deoxys", "year": 2005, "tier": 2,
     "aliases": ["ex deoxys", "deoxys"]},
    {"name": "EX Dragon Frontiers", "year": 2006, "tier": 2,
     "aliases": ["dragon frontiers", "ex dragon frontiers"]},
    {"name": "Expedition Base Set", "year": 2002, "tier": 2,
     "aliases": ["expedition", "expedition base"]},
    {"name": "Neo Destiny", "year": 2002, "tier": 2, "aliases": ["neo destiny"]},
    {"name": "EX Holon Phantoms", "year": 2006, "tier": 2,
     "aliases": ["holon phantoms", "holon"]},
    {"name": "Evolving Skies", "year": 2021, "tier": 2,
     "aliases": ["evolving skies"]},
]

# --- the individual CARDS he named (prompts.md lines 82-96) -----------------
# ``query`` keeps the spelling that actually finds them on FINN; ``aliases``
# include the seller-typo forms (spec §1.5 — typos are where deals hide).
CARDS: list[dict[str, Any]] = [
    {"name": "Umbreon", "query": "umbreon", "aliases": ["umbreon", "umbreum"]},
    {"name": "Gengar", "query": "gengar", "aliases": ["gengar"]},
    {"name": "Mew", "query": "mew", "aliases": ["mew"]},
    {"name": "Mewtwo", "query": "mewtwo", "aliases": ["mewtwo", "mew2", "mew two"]},
    {"name": "Ho-Oh", "query": "ho-oh", "aliases": ["ho-oh", "ho oh", "hooh"]},
    {"name": "Lugia", "query": "lugia", "aliases": ["lugia"]},
    {"name": "Pikachu", "query": "pikachu", "aliases": ["pikachu", "pikatchu"]},
    {"name": "Jolteon", "query": "jolteon", "aliases": ["jolteon"]},
    {"name": "Alakazam", "query": "alakazam", "aliases": ["alakazam", "alakhazam"]},
    {"name": "Rayquaza", "query": "rayquaza", "aliases": ["rayquaza", "rayquasa", "rayquazar"]},
    {"name": "Mightyena", "query": "mightyena", "aliases": ["mightyena"]},
    {"name": "Dragonair", "query": "dragonair", "aliases": ["dragonair", "dragenair"]},
    {"name": "Typhlosion", "query": "typhlosion", "aliases": ["typhlosion", "typhhlosion", "typhlosion"]},
    {"name": "Raichu", "query": "raichu", "aliases": ["raichu"]},
]

# --- the BROAD phrases he types (prompts.md lines 74-80) --------------------
BROAD: list[dict[str, Any]] = [
    {"label": "Pokemon Kort", "query": "pokemon kort", "tier": 3},
    {"label": "Pokemonkort", "query": "pokemonkort", "tier": 3},
    {"label": "Vintage Pokemon Kort", "query": "vintage pokemon kort", "tier": 3},
    {"label": "Pokemon Samling", "query": "pokemon samling", "tier": 3},
    {"label": "Pokemon Kort Holo", "query": "pokemon kort holo", "tier": 3},
    {"label": "Japanske Pokemon Kort", "query": "japanske pokemon kort", "tier": 3},
]


# --------------------------------------------------------------------------- #
# Search-definition builders
# --------------------------------------------------------------------------- #


def _slug(text: str) -> str:
    """Lowercase, dash-separated, ASCII slug (matches finnlib.slugify closely)."""
    out = []
    prev_dash = False
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    return "".join(out).strip("-")


def broad_defs() -> list[dict[str, Any]]:
    defs = []
    for b in BROAD:
        defs.append({
            "id": f"broad-{_slug(b['query'])}",
            "kind": "broad",
            "label": b["label"],
            "query": b["query"],
            "tier": b["tier"],
            "params": dict(CARD_PARAMS),
            "sorts": list(DEFAULT_SORTS),
            "max_pages": 2,
        })
    return defs


def set_defs(tier: int | None = None) -> list[dict[str, Any]]:
    defs = []
    for s in SETS:
        if tier is not None and s["tier"] != tier:
            continue
        defs.append({
            "id": f"set-{_slug(s['name'])}",
            "kind": "set",
            "label": s["name"],
            "query": s["name"].split(" (", 1)[0],   # "Base Set (1st Edition…)" -> "Base Set"
            "tier": s["tier"],
            "set_name": s["name"],
            "year": s.get("year"),
            "aliases": s["aliases"],
            "params": dict(CARD_PARAMS),
            "sorts": ["PUBLISHED_DESC"],
            "max_pages": 2,
        })
    return defs


def card_defs() -> list[dict[str, Any]]:
    defs = []
    for c in CARDS:
        defs.append({
            "id": f"card-{_slug(c['name'])}",
            "kind": "card",
            "label": c["name"],
            "query": c["query"],
            "tier": 2,
            "aliases": c["aliases"],
            "params": dict(CARD_PARAMS),
            "sorts": ["PUBLISHED_DESC"],
            "max_pages": 1,
        })
    return defs


def search_defs(
    kind: str | None = None,
    tier: int | None = None,
    ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Return the requested slice of the catalog.

    ``kind`` ∈ {broad, set, card, all/None}. ``tier`` filters set searches
    (1/2). ``ids`` selects specific search ids (e.g. for a targeted re-run).
    """
    kind = (kind or "all").lower()
    out: list[dict[str, Any]] = []
    if kind in ("all", "broad"):
        out += broad_defs()
    if kind in ("all", "set", "sets"):
        out += set_defs(tier)
    if kind in ("all", "card", "cards"):
        # tier filter only makes sense for sets; cards are always "interesting"
        out += card_defs() if tier is None else []
    if ids is not None:
        wanted = set(ids)
        out = [d for d in out if d["id"] in wanted]
    return out


def catalog() -> dict[str, Any]:
    """The full machine catalog (what ``--json`` prints / the scraper loads)."""
    return {
        "card_params": CARD_PARAMS,
        "sorts": DEFAULT_SORTS,
        "sets": SETS,
        "cards": CARDS,
        "broad": BROAD,
        "searches": search_defs("all"),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _print_table(defs: list[dict[str, Any]]) -> None:
    print(f"{'id':<34} {'kind':<6} {'tier':<4} {'pages':<5} {'query':<24} sorts")
    print("-" * 110)
    for d in defs:
        print(f"{d['id']:<34} {d['kind']:<6} {d['tier']:<4} {d['max_pages']:<5} "
              f"{d['query']:<24} {','.join(d['sorts'])}")
    kinds: dict[str, int] = {}
    for d in defs:
        kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
    print("-" * 110)
    print(f"total searches: {len(defs)}  ({', '.join(f'{k}={v}' for k, v in sorted(kinds.items()))})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="print a human table")
    parser.add_argument("--json", action="store_true", help="print the machine catalog")
    parser.add_argument("--kind", choices=["broad", "set", "card", "all"], default=None)
    parser.add_argument("--tier", type=int, choices=[1, 2, 3], default=None)
    parser.add_argument("--id", action="append", dest="ids", default=None,
                        help="only these search ids (repeatable)")
    args = parser.parse_args(argv)

    if args.json:
        if args.kind or args.tier or args.ids:
            print(json.dumps(search_defs(args.kind, args.tier, args.ids), indent=2, ensure_ascii=False))
        else:
            print(json.dumps(catalog(), indent=2, ensure_ascii=False))
        return 0

    defs = search_defs(args.kind, args.tier, args.ids)
    if args.list or not args.json:
        _print_table(defs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
