# 0010 — Populate the Google Sheet FINN tab

**Status:** done
**Date:** 2026-10-08

## Goal

The `FINN` tab in the bound Google Sheet was a **stub** — `build_sheet.py` emitted
`"FINN": {..., "rows": []}` and the sheet only ever held the header row. Populate it
with the archive so the asking price sits next to the PokeWallet market value.

## What was built

- `sheet/build_sheet.py`:
  - `FINN_HEADER` (10 cols) adds a **Ratio** column next to Price/Market/Delta, so the
    "market ÷ asking" headline is visible (Apps Script maps by header name, unaffected).
  - `build_finn()` — row universe = the **archive** (via `finn_corpus.collect`); joins
    the registry for `first_seen`/`last_seen` and the **newest pricing record per kode**
    for matched card + market value + delta + ratio. Best deal (highest ratio) first.
    Missing artifacts → blank cells, never a fabricated `0`; append-only JSONL read with
    `split("\n")` (not `splitlines()`).
  - Wired `tabs["FINN"]` to `build_finn(...)`.
- `tests/test_build_sheet_finn.py` (6 tests) — covers every archived ad becoming a row,
  best-deal-first ordering, newest-record-wins, blank-not-zero, header/row width match,
  and missing artifacts → empty (no crash).

## Evidence

- `uv run tests/test_build_sheet_finn.py` → **6 OK**.
- `uv run sheet/build_sheet.py --print` → `FINN rows=107 cols=10`.
- Push via google-sheets MCP → `updatedRange=FINN!A1:J108`, `updatedRows=108`,
  `updatedColumns=10`, `updatedCells=1080`.
- Read-back confirmed: header + 107 ads present, e.g. row 2 =
  `475878513 | Stort vintage salg… | 100.00 kr | (no card) | 49,483.00 kr |
  -49,383.00 kr | 494.83 | Inaktiv`. Apps Script number format already applied.
- Live coverage at push time: 1 ad with a market value/ratio (more land as the API
  budget allows); every ad row is present regardless.

## Notes / next

- Colours (Delta<0 green = deal, Status Aktiv/Inaktiv/Solgt) come from the bound Apps
  Script `finnRules` — run the sheet menu **📊 Portfolio ▸ Format everything** to refresh
  rules/widths after a data change.
- Re-running `build_sheet.py` + re-pushing is the reproducible path; it always
  regenerates from disk, never hand-edits the sheet.
