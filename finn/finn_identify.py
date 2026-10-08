#!/usr/bin/env python3
"""finn_identify.py — work out *which* interesting set/card an ad is.

The FINN pipeline must rank listings by what Marius actually wants.  That intent
already exists, machine-readable, in :mod:`finn_searches` — ``SETS`` (Tier 1 /
Tier 2) and ``CARDS`` (the named Pokémon) with their seller-typo aliases.  This
module reuses that catalog (it never re-hard-codes a list) to answer, for any ad
text: *does this mention an interesting set or card, and how badly do I want it?*

Priority (per ``SCRAPING_PROMPT.md`` §9): Tier-1 sets → named cards → Tier-2 sets;
anything else ranks 0 (not identified as interesting).

Matching is **word-boundary safe** after normalisation, so "mew" does not match
inside "mewtwo" and "Pokémon" matches the alias "pokemon".

CLI
---
  uv run finn/finn_identify.py --title "Skyridge Umbreon holo" --json
  uv run finn/finn_identify.py --title "..." --description-file desc.txt
  uv run finn/finn_identify.py --from-jsonl data/finn/searches/<run>/all_ads.jsonl
  uv run finn/finn_identify.py --from-jsonl ads.jsonl --out identified.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import finnlib as fl  # noqa: E402  (local sibling module)
import finn_searches as fs  # noqa: E402  (the catalog — single source of truth)

IDENTIFY_VERSION = "finn_identify/1.0.0"

# Characters that NFKD does not decompose but Norwegian text uses.
_EXTRA_FOLD = str.maketrans({"ø": "o", "æ": "ae", "Ø": "o", "Æ": "ae", "đ": "d", "ð": "d", "þ": "th"})


def normalize(text: Any) -> str:
    """Lower-case, fold diacritics, and reduce punctuation/whitespace to single spaces.

    ``"Pokémon"`` → ``"pokemon"``, ``"Ho-Oh"`` → ``"ho oh"``, ``"  1st. edition "`` → ``"1st edition"``.
    """
    if not text:
        return ""
    s = str(text).translate(_EXTRA_FOLD)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


_ALIAS_RE_CACHE: dict[str, re.Pattern[str]] = {}


def _alias_re(alias: str) -> re.Pattern[str]:
    """Compiled, word-boundary-safe matcher for a normalised alias phrase."""
    key = normalize(alias)
    rx = _ALIAS_RE_CACHE.get(key)
    if rx is None:
        rx = re.compile(r"(?<![a-z0-9])" + re.escape(key) + r"(?![a-z0-9])")
        _ALIAS_RE_CACHE[key] = rx
    return rx


# Pre-compile the catalog into (item, alias, pattern) triples once.
_SET_ALIASES: list[tuple[dict[str, Any], str, re.Pattern[str]]] = [
    (s, a, _alias_re(a)) for s in fs.SETS for a in s["aliases"]
]
_CARD_ALIASES: list[tuple[dict[str, Any], str, re.Pattern[str]]] = [
    (c, a, _alias_re(a)) for c in fs.CARDS for a in c["aliases"]
]

TIER_LABELS = {1: "tier1-set", 2: "named-card", 3: "tier2-set", 0: "none"}


def _find(text_norm: str, table: list[tuple[dict[str, Any], str, re.Pattern[str]]],
          kind: str) -> list[dict[str, Any]]:
    """Return de-duplicated matches (by item name), best alias first."""
    hits: dict[str, dict[str, Any]] = {}
    for item, alias, rx in table:
        if rx.search(text_norm):
            name = item["name"]
            if name not in hits:
                hits[name] = {
                    "name": name,
                    "kind": kind,
                    "alias": alias,
                    "tier": item.get("tier"),
                    "year": item.get("year"),
                }
    return sorted(hits.values(), key=lambda h: (h["tier"] if h["tier"] is not None else 99, h["name"]))


def find_set_matches(text: Any) -> list[dict[str, Any]]:
    return _find(normalize(text), _SET_ALIASES, "set")


def find_card_matches(text: Any) -> list[dict[str, Any]]:
    return _find(normalize(text), _CARD_ALIASES, "card")


def _best_tier(sets: list[dict[str, Any]]) -> int | None:
    tiers = [s["tier"] for s in sets if s.get("tier") is not None]
    return min(tiers) if tiers else None


def intent_rank(sets: Iterable[dict[str, Any]], cards: Iterable[dict[str, Any]]) -> int:
    """1 = a Tier-1 set matches; 2 = a named card; 3 = a Tier-2 set; 0 = nothing interesting."""
    sets = list(sets)
    cards = list(cards)
    if any(s.get("tier") == 1 for s in sets):
        return 1
    if cards:
        return 2
    if any(s.get("tier") == 2 for s in sets):
        return 3
    return 0


def identify(text: Any) -> dict[str, Any]:
    """Identify the interesting sets/cards in a blob of text."""
    tn = normalize(text)
    sets = _find(tn, _SET_ALIASES, "set")
    cards = _find(tn, _CARD_ALIASES, "card")
    rank = intent_rank(sets, cards)
    return {
        "identify_version": IDENTIFY_VERSION,
        "matched_set_names": [s["name"] for s in sets],
        "matched_card_names": [c["name"] for c in cards],
        "sets": sets,
        "cards": cards,
        "best_tier": _best_tier(sets),
        "intent_rank": rank,
        "intent": TIER_LABELS[rank],
    }


def _record_text(record: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("title", "heading"):
        if record.get(key):
            parts.append(str(record[key]))
    if record.get("description_raw"):
        parts.append(str(record["description_raw"]))
    bc = record.get("breadcrumbs")
    if isinstance(bc, list):
        parts.append(" ".join(str(b) for b in bc))
    return "\n".join(parts)


def identify_ad(record: dict[str, Any]) -> dict[str, Any]:
    """Identify an ad/listing record (accepts both finn_ad and finn_search shapes)."""
    return identify(_record_text(record))


def annotate(row: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``row`` with an added ``identify`` object (input not mutated)."""
    out = dict(row)
    out["identify"] = identify_ad(row)
    return out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--title", help="ad title/heading to identify")
    parser.add_argument("--text", help="arbitrary text to identify")
    parser.add_argument("--description-file", metavar="FILE",
                        help="read extra description text from a file")
    parser.add_argument("--from-jsonl", metavar="FILE",
                        help="annotate every JSON row in a JSONL file with an 'identify' object")
    parser.add_argument("--out", metavar="FILE",
                        help="with --from-jsonl: write annotated rows here (default: stdout)")
    parser.add_argument("--json", action="store_true", help="print the identify result as JSON")
    args = parser.parse_args(argv)

    if args.from_jsonl:
        rows = _load_rows(Path(args.from_jsonl))
        annotated = [annotate(r) for r in rows]
        dist: dict[int, int] = {}
        for a in annotated:
            r = a["identify"]["intent_rank"]
            dist[r] = dist.get(r, 0) + 1
        if args.out:
            out = fl.unique_path(args.out)
            for a in annotated:
                fl.append_jsonl(out, a)
            print(f"annotated {len(annotated)} rows -> {out}")
        else:
            for a in annotated:
                print(json.dumps(a["identify"], ensure_ascii=False))
        print("intent distribution: " + ", ".join(
            f"{TIER_LABELS.get(r, r)}={dist[r]}" for r in sorted(dist, reverse=True)
        ))
        return 0

    parts = [args.title or "", args.text or ""]
    if args.description_file:
        parts.append(Path(args.description_file).read_text(encoding="utf-8"))
    text = "\n".join(p for p in parts if p)
    if not text.strip():
        parser.error("give --title/--text/--description-file, or --from-jsonl")

    result = identify(text)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"intent_rank={result['intent_rank']} ({result['intent']}) best_tier={result['best_tier']}")
        print(f"  sets : {result['matched_set_names']}")
        print(f"  cards: {result['matched_card_names']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
