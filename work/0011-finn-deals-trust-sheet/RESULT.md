# 0011 — Trust-gated FINN deal table + 11-column sheet push

**Status:** done
**Date:** 2026-10-10

## What was built

- **`finn/finn_deals.py`** — the comprehensive per-ad deal table:
  - `SHEET_COLUMNS` = `FINN-kode, Title, Price (NOK), Matched card, Market price, Delta,
    Ratio, Status, First seen, Last seen, Confidence`. **Confidence is LAST** on purpose:
    the bound Apps Script colours by header *name*, and putting Confidence in the middle
    shifted Status/dates out of alignment. Last = Status stays in **H**, dates in **I/J**.
  - `sheet_rows()` blanks `Matched card` / `Market price` / `Delta` / `Ratio` unless the row
    is trusted (`high` / `medium`) — the sheet never *asserts* an untrusted price.
  - **Number-compatibility trust gate** (`number_parts` / `number_conflict`): if the ad's own
    number disagrees with the matched card's number (`05/30` vs `005/026` — the denominator
    `finn_matcher.number_norm` throws away), the row is kept but dropped to `low` and its
    value blanked. This is the core of "we must be able to TRUST the system".
  - `card_confidence()` / `row_confidence()` aggregate the priced cards (majority rule) for a
    card-list sum, or keep the listing confidence for a single match.
- **`tests/test_finn_deals.py`** — 20 tests (pricing selection, the number gate, sheet
  mapping for trusted/untrusted rows, ordering, priority emission, artifact round-trip).
- **`sheet/finn_payload.py`** — turns `finn_sheet_<ts>.csv` into the exact
  `update_cells` payload (range + 2-D array), so nothing is retyped by hand. `--rows` also
  writes one compact JSON array per line (header first) for exact MCP pasting.
- **`sheet/AppScript.gs`** — two fixes (below).

## Evidence

- `uv run tests/test_finn_deals.py` → **20 tests OK**.
- `uv run finn/finn_deals.py` → wrote `data/finn/tables/finn_sheet_2026-10-10-113930.csv`
  (**108 lines = header + 107 ads**), plus `.html` / `.jsonl` / `summary_*.json`.
  Summary at that run: `by_confidence { high: 34, medium: 4, low: 14, none: 55 }`,
  `priced 40`, `with_ratio 7`.
- `uv run sheet/finn_payload.py --csv data/finn/tables/finn_sheet_2026-10-10-113930.csv …`
  → `range: A1:K108`, `shape: 108 rows x 11 cols`, header ends with `Confidence`.
- **Push (google-sheets MCP `update_cells`)** → `updatedRange: FINN!A1:K108`,
  `updatedRows: 108`, `updatedColumns: 11`, `updatedCells: 1188`.
- **Read-back (`get_sheet_data`)** → header
  `… | Status | First seen | Last seen | Confidence`; Status in **H** with
  Aktiv/Solgt/Inaktiv; Price/Market/Delta render as `100.00 kr` / `47,522.00 kr` /
  `-47,422.00 kr`; Delta cell auto-coloured green (below market = a deal).
- `node --check` on the edited `sheet/AppScript.gs` → `APPS_SCRIPT_SYNTAX_OK`.

## Bugs fixed

### 1. `formatEverything` crashed (operator-reported)

```
Exception: You cannot add alternating background colors to a range that already has
alternating background colors.
```

`styleDataSheet()` called `applyRowBanding()` **without clearing the existing banding**.
Because the header also gained a column (10 → 11), the newly-banded range *overlapped* the
old one, so Sheets refused it. Fix — make the step idempotent:

```js
sh.getBandings().forEach(function (b) { b.remove(); });
if (lastRow >= 2) {
  sh.getRange(2, 1, lastRow - 1, lastCol)
    .applyRowBanding(SpreadsheetApp.BandingTheme.LIGHT_GREY, false, false);
}
```

### 2. New `Confidence` column was unstyled

Added a `finnRules` block colour-coding it (by header name):
`high` → green, `medium` → amber, `low` → red, `none` → grey.

## Open follow-ups / known divergence

- **Presentation is manual.** The MCP writes **values only**, and the bound Apps Script has
  **no `doGet`/`doPost`** (no programmatic entry point, no clasp in-repo). So after a data
  change the operator must **re-paste `sheet/AppScript.gs`** into *Extensions ▸ Apps Script*
  and run **📊 Portfolio ▸ Format everything** (or rely on the daily 06:00 trigger) for the
  header band to cover column K and the new Confidence colours to apply. Verified only by
  syntax-check + logic; the rendered result is pending that operator step.
- **Legacy path:** `sheet/build_sheet.py` still has its **own** `FINN_HEADER` (10 cols) and
  `build_finn()` with a *different* matched-card semantic (`basis: card_list_sum` →
  `listing.best.name`), covered by `tests/test_build_sheet_finn.py` (asserts 10 cols). It was
  deliberately **left untouched**: editing it would force test edits and change a documented
  contract. `finn/finn_deals.py` is the **authoritative** FINN emitter — do **not** run
  `build_sheet.py` to refresh `FINN` unless/until the two are deliberately reconciled.
