#!/usr/bin/env python3
"""finn_cards.py — structure enumerated card lists out of an ad description.

Some FINN ads don't sell *a* card — they enumerate many.  Where the description
contains a list ("Liste over kort:" or a bulleted/numbered run) we turn it into
per-card records that keep their **provenance** (the source line index), and we
*reconcile counts loudly*: a listing titled "79 stk" whose description says
"99 stk" is a real thing, and it must be surfaced, never silently resolved
(``SCRAPING_PROMPT.md`` §5.4 / §11).

Extraction is deterministic and verbatim — no LLM, no spell-correction here.
Matching these cards to PokeWallet and pricing them is a separate stage.

CLI
---
  uv run finn/finn_cards.py --json data/finn/annonser/475878513_.../475878513.json
  uv run finn/finn_cards.py --title "79 stk Pokemon kort" --file desc.txt
  uv run finn/finn_cards.py --from-jsonl data/finn/searches/<run>/all_ads.jsonl [--out out.jsonl]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import finnlib as fl  # noqa: E402  (local sibling module)

CARDS_VERSION = "finn_cards/1.0.0"

# Markers that introduce an enumerated list (matched case-insensitively).
_BLOCK_MARKERS = [
    r"liste\s+over\s+kort",
    r"kortliste",
    r"full\s+liste",
    r"her\s+er\s+lista",
    r"kort\s+jeg\s+har",
    r"cards?\s*:",
    r"kort\s*:",
]
_BLOCK_RE = re.compile("|".join(_BLOCK_MARKERS), re.I)

# Lines after the list that are clearly boilerplate, not cards.
_STOP_RE = re.compile(
    r"^\s*(frakt|sendes|kan\s+sendes|sending|betaling|betaler|kontakt|ring|sms|"
    r"møtes|motes|hentes|pris|köpa|kopa|velkommen|hilsen)\b",
    re.I,
)
# Variant tokens (longest first so "reverse holo" wins over "holo").
_VARIANTS = [
    "reverse holo", "rev holo", "rev. holo", "reverse-holo",
    "1st edition", "first edition", "1st ed", "shadowless",
    "holo", "psa", "rh",
]
_VARIANT_RE = re.compile(
    r"\b(" + "|".join(re.escape(v) for v in _VARIANTS) + r")\b", re.I
)
# Per-line count: leading "4x"/"4 x"/"x4 -" or trailing "x3"/"(x3)"/"- 3 stk".
_LEAD_COUNT_RE = re.compile(r"^\s*(\d{1,3})\s*[x×]\s+", re.I)
_TRAIL_COUNT_RE = re.compile(r"[\s(\[]*[x×]\s*(\d{1,3})[\s)\]]*$", re.I)
# Stated totals in title/description: "79 stk", "260+", "534 kort", "80x kort".
_COUNT_UNIT_RE = re.compile(r"(\d{1,4})\s*(?:stk\b|st\.?\b|kort\b|korta\b|pieces\b|cards?\b|stk\.)", re.I)
_COUNT_PLUS_RE = re.compile(r"(\d{2,4})\s*\+")
_COUNT_TIMES_RE = re.compile(r"\b(\d{2,4})\s*[x×]\s*(?:kort\b|cards?\b)", re.I)

_WORD_OK_RE = re.compile(r"^[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9'’.\- ]*$")

# Every Unicode boundary that ``str.splitlines()`` honours but ``"\n"`` does not.
_LINE_BREAKS = ("\r\n", "\r", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85",
                "\u2028", "\u2029")


def logical_lines(text: str) -> list[str]:
    """Normalize every Unicode line boundary to ``\\n``, then split.

    Scraped ad text carries LS/PS/CR/VT/FF/NEL.  ``str.splitlines`` honours them
    but ``str.count("\\n")`` does not — mixing the two silently desynchronises the
    ``line_index`` we keep as card provenance.  (Found on the real capture: a single
    ``U+2028`` in the ad prose shifted every card index by one.)
    """
    for br in _LINE_BREAKS:
        text = text.replace(br, "\n")
    return text.split("\n")


def _looks_like_card_name(name: str) -> bool:
    """Cheap guard so prose/boilerplate lines are not mistaken for cards."""
    s = name.strip()
    if not (1 <= len(s) <= 40):
        return False
    if s.isdigit():
        return False
    if ":" in s:
        return False
    words = s.split()
    if not (1 <= len(words) <= 6):
        return False
    if not _WORD_OK_RE.match(s):
        return False
    # Reject lines that are clearly a sentence (ending punctuation).
    if s.endswith((",", ";", "?")) or s.endswith(".") and len(words) > 3:
        return False
    return True


def parse_card_line(line: str, line_index: int) -> dict[str, Any] | None:
    """Parse one description line into a card record (or ``None`` if not a card)."""
    raw = line.rstrip()
    s = raw.strip()
    if not s or _STOP_RE.match(s):
        return None
    # strip list bullets / numbering
    s = re.sub(r"^[\-\*\u2022·]\s*", "", s)
    s = re.sub(r"^\d{1,3}[.)]\s+", "", s)
    s = s.strip()

    # A bare total ("99 stk", "534 kort") is a count statement, not a card.
    if re.fullmatch(r"\d{1,4}\s*(?:stk\.?|st\.?|kort|korta|cards?|pieces)", s, re.I):
        return None

    count = 1
    m = _LEAD_COUNT_RE.match(s)
    if m:
        count = int(m.group(1))
        s = s[m.end():].strip()
    else:
        m = _TRAIL_COUNT_RE.search(s)
        if m:
            count = int(m.group(1))
            s = s[: m.start()].strip()

    variants = [v.lower() for v in _VARIANT_RE.findall(s)]
    name = _VARIANT_RE.sub(" ", s)
    name = re.sub(r"\s{2,}", " ", name).strip(" -–—")

    if not _looks_like_card_name(name):
        return None
    return {
        "name": name,
        "count": count,
        "variants": sorted(set(variants)),
        "raw": raw,
        "line_index": line_index,
    }


_BULLET_RE = re.compile(r"^\s*(?:[\-\*\u2022·]|\d{1,3}[.)])\s+")


def find_card_list_block(description: str) -> dict[str, Any] | None:
    """Locate the enumerated list: an explicit marker, else a long bullet/`number` run."""
    if not description:
        return None
    lines = logical_lines(description)
    norm = "\n".join(lines)
    m = _BLOCK_RE.search(norm)
    if m:
        start = m.end()
        # skip the rest of the marker line / immediate punctuation
        nl = norm.find("\n", start)
        if nl != -1 and norm[start:nl].strip() in ("", ":", "-"):
            start = nl + 1
        return {
            "marker": norm[m.start():m.end()].strip(),
            "block": norm[start:],
            "start_line_index": norm[:start].count("\n"),
        }

    # No marker: accept a run of >= 8 explicit bullet/numbered lines that parse as cards.
    best: tuple[int, int] | None = None
    run_start: int | None = None
    for i, line in enumerate(lines):
        is_item = bool(_BULLET_RE.match(line)) and parse_card_line(line, i) is not None
        if is_item:
            if run_start is None:
                run_start = i
        elif run_start is not None:
            if best is None or (i - run_start) > best[1]:
                best = (run_start, i - run_start)
            run_start = None
    if run_start is not None and (best is None or (len(lines) - run_start) > best[1]):
        best = (run_start, len(lines) - run_start)
    if best and best[1] >= 8:
        start = best[0]
        return {
            "marker": "(bullet/numbered run)",
            "block": "\n".join(lines[start:]),
            "start_line_index": start,
        }
    return None


def parse_card_list(description: str) -> dict[str, Any]:
    """Structure the enumerated card list in a description, with provenance."""
    block = find_card_list_block(description)
    if not block:
        return {"card_list_present": False, "marker": None, "cards": [],
                "card_line_count": 0, "card_count": 0}
    cards: list[dict[str, Any]] = []
    for i, line in enumerate(logical_lines(block["block"])):
        rec = parse_card_line(line, block["start_line_index"] + i)
        if rec:
            cards.append(rec)
    return {
        "card_list_present": len(cards) > 0,
        "marker": block["marker"],
        "cards": cards,
        "card_line_count": len(cards),
        "card_count": sum(c["count"] for c in cards),
    }


def extract_counts(text: str) -> list[int]:
    """Stated card totals in a title/description: ``79 stk``, ``260+``, ``534 kort``, ``80x kort``."""
    if not text:
        return []
    found: set[int] = set()
    for rx in (_COUNT_UNIT_RE, _COUNT_PLUS_RE, _COUNT_TIMES_RE):
        for m in rx.finditer(text):
            found.add(int(m.group(1)))
    return sorted(found)


def structure(record: dict[str, Any]) -> dict[str, Any]:
    """Full per-ad card structuring + loud reconciliation flags."""
    desc = record.get("description_raw") or ""
    title = record.get("title") or record.get("heading") or ""

    parsed = parse_card_list(desc)
    stated_title = extract_counts(title)
    stated_desc = extract_counts(desc)

    flags: list[str] = []
    if len(set(stated_title) | set(stated_desc)) > 1:
        flags.append(
            f"stated counts disagree: title={stated_title} description={stated_desc}"
        )
    if stated_title and parsed["card_list_present"]:
        for s in stated_title:
            if s != parsed["card_line_count"]:
                flags.append(
                    f"title states {s} cards but description enumerates "
                    f"{parsed['card_line_count']}"
                )
    if stated_desc and parsed["card_list_present"]:
        for s in stated_desc:
            if s != parsed["card_line_count"] and s not in stated_title:
                flags.append(
                    f"description states {s} cards but enumerates {parsed['card_line_count']}"
                )

    return {
        "cards_version": CARDS_VERSION,
        "finn_kode": record.get("finn_kode"),
        "card_list_present": parsed["card_list_present"],
        "marker": parsed["marker"],
        "cards": parsed["cards"],
        "card_line_count": parsed["card_line_count"],
        "card_count": parsed["card_count"],
        "stated_title_counts": stated_title,
        "stated_description_counts": stated_desc,
        "flags": flags,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _print_summary(res: dict[str, Any]) -> None:
    print(f"finn_kode={res['finn_kode']} card_list_present={res['card_list_present']} "
          f"marker={res['marker']!r}")
    print(f"  card_line_count={res['card_line_count']}  card_count(sum)={res['card_count']}")
    print(f"  stated_title={res['stated_title_counts']}  "
          f"stated_description={res['stated_description_counts']}")
    for f in res["flags"]:
        print(f"  FLAG: {f}")
    for c in res["cards"][:10]:
        print(f"    [{c['line_index']:>3}] {c['name']!r} x{c['count']} {c['variants']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--json", metavar="FILE", help="a parsed ad record JSON (from finn_ad.py)")
    parser.add_argument("--title", help="ad title (for count reconciliation)")
    parser.add_argument("--file", metavar="FILE", help="a description text file")
    parser.add_argument("--from-jsonl", metavar="FILE", help="structure every record in a JSONL file")
    parser.add_argument("--out", metavar="FILE", help="with --from-jsonl: write structured rows here")
    args = parser.parse_args(argv)

    if args.from_jsonl:
        rows = _load_rows(Path(args.from_jsonl))
        structured = [structure(r) for r in rows]
        with_list = sum(1 for s in structured if s["card_list_present"])
        total_cards = sum(s["card_line_count"] for s in structured)
        flagged = sum(1 for s in structured if s["flags"])
        if args.out:
            out = fl.unique_path(args.out)
            for s in structured:
                fl.append_jsonl(out, s)
            print(f"structured {len(structured)} ads -> {out}")
        else:
            for s in structured:
                _print_summary(s)
        print(f"SUMMARY: ads={len(structured)} with_card_list={with_list} "
              f"card_lines={total_cards} flagged={flagged}")
        return 0

    if args.json:
        record = json.loads(Path(args.json).read_text(encoding="utf-8"))
    else:
        desc = Path(args.file).read_text(encoding="utf-8") if args.file else ""
        record = {"title": args.title or "", "description_raw": desc, "finn_kode": None}
    if not (record.get("description_raw") or record.get("title")):
        parser.error("give --json, or --title/--file")

    res = structure(record)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
