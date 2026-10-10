#!/usr/bin/env python3
"""Emit the FINN-tab 2-D array (JSON) for the google-sheets MCP push.

The google-sheets MCP server is the only authenticated write path (see
``sheet/build_sheet.py``). Its ``update_cells`` tool takes a range plus a 2-D
array of values inline, so this script turns a ``finn_sheet_<ts>.csv`` (written
by ``finn/finn_deals.py``) into exactly that payload, so the push is
reproducible and no value is retyped by hand.

Reads the CSV with the standard library ``csv`` module, so titles containing
embedded newlines or commas survive intact.

Run:
    uv run sheet/finn_payload.py --csv data/finn/tables/finn_sheet_<ts>.csv
    uv run sheet/finn_payload.py --csv <...> --out sheet/out/finn_payload_<ts>.json

Nothing is deleted or overwritten unless ``--out`` names an explicit new file.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def read_matrix(path: Path) -> list[list[str]]:
    """Read the CSV into a list-of-lists (header row included)."""
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [row for row in csv.reader(fh)]


def column_letter(n: int) -> str:
    """1 -> 'A', 27 -> 'AA' (for building the A1 range)."""
    out = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="finn_sheet_<ts>.csv to emit")
    parser.add_argument("--sheet", default="FINN", help="tab name (default: FINN)")
    parser.add_argument("--out", default=None, help="write JSON here instead of stdout")
    parser.add_argument("--rows", default=None,
                        help="also write one compact JSON array per line (header first)")
    args = parser.parse_args(argv)

    path = Path(args.csv)
    if not path.exists():
        print(f"[finn_payload] ERROR: {path} does not exist", file=sys.stderr)
        return 2

    rows = read_matrix(path)
    if not rows:
        print(f"[finn_payload] ERROR: {path} is empty", file=sys.stderr)
        return 2

    n_rows = len(rows)
    n_cols = max(len(r) for r in rows)
    for r in rows:                       # pad short rows so every row is rectangular
        if len(r) < n_cols:
            r.extend([""] * (n_cols - len(r)))

    rng = f"A1:{column_letter(n_cols)}{n_rows}"
    payload = {"sheet": args.sheet, "range": rng, "data": rows}

    # Report what will actually be pushed (never claim success without counts).
    print(f"[finn_payload] csv    : {path}")
    print(f"[finn_payload] sheet  : {args.sheet}")
    print(f"[finn_payload] range  : {rng}")
    print(f"[finn_payload] shape  : {n_rows} rows x {n_cols} cols")
    print(f"[finn_payload] header : {rows[0]}")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        # Indented so a single row never becomes one ultra-long line (which the
        # file reader would truncate); still plain, valid JSON.
        text = json.dumps(payload, ensure_ascii=False, indent=1)
        out.write_text(text, encoding="utf-8")
        print(f"[finn_payload] wrote  : {out} ({len(text)} bytes)")
    else:
        print("[finn_payload] payload:")
        print(json.dumps(payload, ensure_ascii=False))

    if args.rows:
        rp = Path(args.rows)
        rp.parent.mkdir(parents=True, exist_ok=True)
        # One compact JSON array per line: each line stays well under the file
        # reader's line limit, so rows can be copied verbatim into the MCP call.
        with rp.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[finn_payload] rows   : {rp} ({n_rows} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
