#!/usr/bin/env python3
"""Print the scraped ad descriptions in readable form.

Stdlib only -- it reads ads_extract.json and wraps text.

Usage
  uv run data/photos-receives-2026-11-08-224643/dump_desc.py            # all
  uv run data/photos-receives-2026-11-08-224643/dump_desc.py 480587158 479522079
  uv run data/photos-receives-2026-11-08-224643/dump_desc.py --core     # JP sealed boxes only
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "ads_extract.json"


def main(argv: list[str]) -> int:
    records = json.loads(SRC.read_text(encoding="utf-8"))
    by_kode = {r["finn_kode"]: r for r in records}

    if "--core" in argv:
        sel = [r for r in records
               if r["language"] == "JP" and r["product"] == "booster box"
               and not r["other_tcg"] and r["price_nok"] and r["price_nok"] >= 100]
    elif argv:
        sel = [by_kode[k] for k in argv if k in by_kode]
        unknown = [k for k in argv if k not in by_kode]
        if unknown:
            print(f"unknown koder: {unknown}")
    else:
        sel = records

    for r in sorted(sel, key=lambda r: (r["set"] or "zzz", r["finn_kode"])):
        print("=" * 100)
        print(f"{r['finn_kode']}  {r['price_nok']:,} NOK  lot={r['boxes_in_lot']}  "
              f"per box={r['price_per_box']}  {r['language']}  {r['product']}  "
              f"{r['seller_segment']}  set={r['set']}")
        print(f"  {r['title']}")
        print(f"  {r['location']}  ·  modified {r['last_modified']}  ·  "
              f"status {r['status']}  ·  condition {r['condition']!r}  ·  "
              f"images {r['gallery_count']}  ·  desc {r['desc_len']} chars")
        print("-" * 100)
        if r["desc"]:
            for line in r["desc"].splitlines():
                print(textwrap.fill(line, 98) if line.strip() else "")
        else:
            print("(no description)")
        print()
    print(f"{len(sel)} ad(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
