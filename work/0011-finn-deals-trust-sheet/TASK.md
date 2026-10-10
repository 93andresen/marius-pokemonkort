# TASK 0011 — Trust-gated FINN deal table + 11-column sheet push

- **Status:** done
- **Owner:** agent
- **Output artifact(s):** `finn/finn_deals.py` (+ `tests/test_finn_deals.py`),
  `sheet/finn_payload.py`, `data/finn/tables/finn_sheet_<ts>.csv`, the bound Sheet's
  `FINN` tab, `sheet/AppScript.gs`
- **Depends on:** 0008 (bulk scrape), 0009 (archive→records join), 0010 (FINN tab existed)

## Goal (one sentence)

Assemble **one trustworthy row per archived FINN ad** — asking price beside the PokeWallet
market value, an explicit *confidence* verdict, and a number-compatibility trust gate that
never asserts a wrong card — push all rows to the bound Sheet's `FINN` tab, and make the
sheet's Apps Script format the result cleanly.

## Why / context

The raw inputs are the append-only artifacts the earlier items produced:

- `data/finn/annonser/<kode>_<slug>/<kode>.json` — the ad **archive** (row universe).
- `data/finn/registry/pokemon-kort.json` — `first_seen` / `last_seen` per kode.
- `data/finn/matches/pricing.jsonl` + `matches.jsonl` — newest pricing record per kode
  (matched card, market value, delta, ratio). *(Read the newest per kode; `split("\n")`,
  never `splitlines()` — U+2028 occurs inside real FINN descriptions.)*

The trust requirement dominates: it is **far** more important that the table be
believable than big. A match whose card number contradicts the ad's own number is a
*different* card — it must be kept but dropped to `low` confidence, and the Sheet must
blank its card + market value rather than assert a wrong price.

## In scope

- `finn/finn_deals.py`: `SHEET_COLUMNS` (11) + `sheet_rows()` (metadata, Confidence **last**
  so the name-keyed Sheet formatting keeps Status in H and the dates in I/J).
- The number-compatibility **trust gate** (`number_parts` / `number_conflict`) inside
  `build_rows`; `card_confidence` / `row_confidence`.
- `sheet/finn_payload.py`: a CSV → exact google-sheets-MCP payload emitter (so no cell is
  retyped by hand); `--rows` emits one compact JSON array per line.
- Pushing `FINN!A1:K108` via the google-sheets MCP; verifying the read-back.
- `sheet/AppScript.gs`: fix the banding crash and colour the new Confidence column.

## Out of scope (do NOT touch)

- `sheet/build_sheet.py`'s own `FINN_HEADER` / `build_finn()` — a **legacy 10-column path**
  with its own tested contract (`tests/test_build_sheet_finn.py`); left untouched (see
  RESULT "Known divergence").
- The PokeWallet budget policy and any other tab's formatting.

## Success criteria (defined before coding)

- [x] One row per archived ad; no ad dropped.
- [x] Card/market/delta/ratio are blank unless the row is trusted (`high`/`medium`).
- [x] A conflicting card number downgrades the row to `low` and blanks its value.
- [x] `SHEET_COLUMNS` order keeps Status at column H and the dates at I/J.
- [x] CSV → MCP payload emitter reproduces the exact 2-D array + A1 range.
- [x] The pushed tab reads back header-ending-in-`Confidence`, Status in H, NOK formats.
- [x] `formatEverything` re-runs without throwing.

## Test plan (written first, under `tests/`)

| Test | Input | Expected |
|---|---|---|
| newest pricing wins | two records for one kode, one priced | priced record chosen |
| number gate | `05/30` vs `005/026` | `number_conflict` true → row `low` |
| sheet mapping (trusted) | `high` row | card/market/delta/ratio present |
| sheet mapping (untrusted) | `low` row | card + value blanked |
| ordering | mixed intents/ratios | intent first, best ratio first |

## Evidence to capture

- `uv run tests/test_finn_deals.py` → all tests OK.
- `uv run finn/finn_deals.py` → prints row/confidence counts + writes the tables.
- `uv run sheet/finn_payload.py --csv …` → prints `A1:K108 · 108 rows x 11 cols`.
- MCP push result + a read-back of `FINN!A1:K2`.
- `node --check` of the edited Apps Script.

## Open questions / assumptions

- Google Sheets **has no web-app entry point** (`doGet`/`doPost` absent) and the MCP writes
  **values only** — so presentation is applied by re-pasting `sheet/AppScript.gs` and
  running **📊 Portfolio ▸ Format everything** (manual; no clasp/API automation in-repo).
