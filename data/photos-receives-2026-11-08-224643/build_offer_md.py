#!/usr/bin/env python3
"""Regenerate offer.md from offer.json, adding a NOK column.

FX: 100 NOK = 1 674,68 JPY (Google, 2026-11-08 22:01 UTC) -> 1 JPY = 0.0597130 NOK.

No third-party dependencies: this only reads a local JSON file and formats a
fixed-width table. Nothing on PyPI does that better than the stdlib.

This script intentionally overwrites offer.md -- that file is its own output.
The write goes through a temp file + os.replace so a crash cannot leave a
half-written table behind.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "offer.json"
OUT = HERE / "offer.md"

NOK_PER_JPY = 100 / 1674.68
FX_NOTE = "100 NOK = 1 674,68 JPY (Google, 2026-11-08 22:01 UTC)"


def to_nok(jpy: int | None) -> int | None:
    return None if jpy is None else round(jpy * NOK_PER_JPY)


def fmt(value: int | None) -> str:
    """Thousands separated by a space (Norwegian convention); '???' when unknown."""
    return "???" if value is None else f"{value:,}".replace(",", " ")


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    items = data["items"]

    rows = []
    for it in items:
        unit_jpy = it["unit_price_jpy"]
        unit_nok = to_nok(unit_jpy)
        rows.append(
            (
                it["set_name"] or "??? (name cropped)",
                it["qty"],
                unit_jpy,
                unit_nok,
                None if unit_jpy is None else unit_jpy * it["qty"],
                None if unit_nok is None else unit_nok * it["qty"],
            )
        )

    total_qty = sum(r[1] for r in rows)
    total_jpy = sum(r[4] for r in rows if r[4] is not None)
    total_nok = sum(r[5] for r in rows if r[5] is not None)

    w_name = max([len(r[0]) for r in rows] + [len("Set"), len("TOTAL")])
    w_qty = max([len(str(r[1])) for r in rows] + [len("Qty"), len(fmt(total_qty))])
    w_jpy = max([len(fmt(r[2])) for r in rows] + [len("JPY/box")])
    w_nok = max([len(fmt(r[3])) for r in rows] + [len("NOK/box")])
    w_jpy_t = max([len(fmt(r[4])) for r in rows] + [len("JPY total"), len(fmt(total_jpy))])
    w_nok_t = max([len(fmt(r[5])) for r in rows] + [len("NOK total"), len(fmt(total_nok))])

    def row(name: str, qty: str, jpy: str, nok: str, jpy_t: str, nok_t: str) -> str:
        return (
            f"{name:<{w_name}}  {qty:>{w_qty}}  {jpy:>{w_jpy}}  {nok:>{w_nok}}"
            f"  {jpy_t:>{w_jpy_t}}  {nok_t:>{w_nok_t}}"
        )

    table = [row("Set", "Qty", "JPY/box", "NOK/box", "JPY total", "NOK total")]
    for name, qty, jpy, nok, line_jpy, line_nok in rows:
        table.append(row(name, str(qty), fmt(jpy), fmt(nok), fmt(line_jpy), fmt(line_nok)))
    table.append("-" * len(table[0]))
    table.append(row("TOTAL", fmt(total_qty), "", "", fmt(total_jpy), fmt(total_nok)))

    md = [
        "# Japanese sealed booster boxes — offer from Kaishi",
        "",
        "Source: 3 Signal screenshots in this folder. Prices are per box.",
        f"FX: {FX_NOTE}.",
        "",
        "```",
        *table,
        "```",
        "",
        f"{fmt(total_qty)} boxes · {fmt(total_jpy)} JPY · {fmt(total_nok)} NOK "
        "(excludes Clay Burst)",
        "",
        "Two lines are cut off by the screenshot edges: the set name on the "
        "25 800 JPY line, and the price on Clay Burst.",
        "",
    ]

    tmp = OUT.with_name(OUT.name + ".tmp")
    tmp.write_text("\n".join(md), encoding="utf-8")
    os.replace(tmp, OUT)

    print(f"fx            : 1 JPY = {NOK_PER_JPY:.7f} NOK  ({FX_NOTE})")
    print(f"rows          : {len(rows)}")
    print(f"priced rows   : {sum(1 for r in rows if r[2] is not None)}")
    print(f"total boxes   : {fmt(total_qty)}")
    print(f"total JPY     : {fmt(total_jpy)}")
    print(f"total NOK     : {fmt(total_nok)}")
    print(f"wrote         : {OUT}  ({len(md)} lines)")


if __name__ == "__main__":
    main()
