#!/usr/bin/env python3
"""Diagnostic: verify card ``line_index`` provenance on the real capture.

Loads the committed real capture (tests/fixtures), parses + structures it exactly
as the tests do, then compares every card's reported ``line_index`` against the
line you get from three different line spaces:

  * ``logical_lines()``   — the module's canonical space (all Unicode line
                            boundaries LS/PS/CR/VT/FF/NEL normalized to "\\n")
  * ``str.splitlines()``  — honours those same boundaries (should agree)
  * ``str.split("\\n")``  — naive: splits on "\\n" only (demonstrates the bug)

The real ad contains a single ``U+2028`` (LINE SEPARATOR) in its prose, which is
why ``split("\\n")`` and the canonical space disagree by one index past that
point.  Mismatches against the *canonical* space must be zero.

Run with:  uv run work/0004-card-list-structuring/check_provenance.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "finn"))

import finn_ad  # noqa: E402
import finn_cards  # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "finn_ad_475878513.html"

EXTRA_BREAKS = {
    "\x0b": "VT", "\x0c": "FF", "\x1c": "FS", "\x1d": "GS", "\x1e": "RS",
    "\r": "CR", "\x85": "NEL", "\u2028": "LS", "\u2029": "PS",
}


def _mismatches(cards: list[dict], lines: list[str]) -> int:
    n = 0
    for c in cards:
        idx = c["line_index"]
        got = lines[idx].strip() if 0 <= idx < len(lines) else "<OUT-OF-RANGE>"
        if got != c["raw"].strip():
            n += 1
    return n


def main() -> int:
    rec = finn_ad.parse_ad(FIXTURE.read_text(encoding="utf-8"))
    desc = rec["description_raw"]
    res = finn_cards.structure(rec)

    canonical = finn_cards.logical_lines(desc)
    by_splitlines = desc.splitlines()
    naive = desc.split("\n")

    print(f"desc length                    = {len(desc)}")
    print(f"count('\\n')                    = {desc.count(chr(10))}")
    print(f"len(logical_lines)  [canonical]= {len(canonical)}")
    print(f"len(splitlines)                = {len(by_splitlines)}")
    print(f"len(split('\\n'))     [naive]   = {len(naive)}")
    print(f"card_line_count                = {res['card_line_count']}")
    print(f"marker                         = {res['marker']!r}")

    hits = [(i, EXTRA_BREAKS[ch]) for i, ch in enumerate(desc) if ch in EXTRA_BREAKS]
    print(f"extra line-boundary chars      = {len(hits)}")
    for i, name in hits[:20]:
        print(f"    offset {i}: {name}")

    print(f"\nmismatches vs canonical (logical_lines) = "
          f"{_mismatches(res['cards'], canonical)} / {len(res['cards'])}"
          f"   <-- MUST be 0")
    print(f"mismatches vs splitlines                = "
          f"{_mismatches(res['cards'], by_splitlines)} / {len(res['cards'])}")
    print(f"mismatches vs naive split('\\n')         = "
          f"{_mismatches(res['cards'], naive)} / {len(res['cards'])}"
          f"   <-- illustrates the pre-fix drift")

    # Eyeball the region around the U+2028 to show the canonical split fixing it.
    ls_off = desc.find("\u2028")
    if ls_off != -1:
        lo = max(0, ls_off - 20)
        print(f"\nraw slice around U+2028 (offset {ls_off}):")
        print(f"    ...{desc[lo:ls_off + 20]!r}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
