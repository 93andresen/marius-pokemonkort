# TASK 0006 — Build the sortable listings + cards tables

- **Status:** in-progress
- **Owner:** Zoo (code mode)
- **Output artifact(s):** `finn/finn_tables.py`, `tests/test_finn_tables.py`
- **Depends on:** 0005 (`finn/finn_price.py` → `data/finn/matches/pricing.jsonl`), `finnlib`
- **Reuses (does NOT re-hard-code):** `finnlib.write_json/ensure_dir/unique_path/ts_now`, stdlib `csv`

## Goal (one sentence)

Turn the append-only `pricing.jsonl` records into the program's headline deliverable: a **listings table**
(one row per ad, with the deal ratio next to the asking price) and a **cards table** (one row per
enumerated card), written as **CSV + a self-contained, client-side-sortable HTML** under
`data/finn/tables/`, so the best deals surface at a glance.

## Why / context

`SCRAPING_PROMPT.md` finished state = "the table(s) … with a deal ratio (`market_value_nok / asking_price_nok`)".
0005 produces the per-ad / per-card numbers; nothing yet assembles them into the human-facing table. This
item is that assembly — deterministic, offline, stdlib-only.

## In scope

- `listing_row(res)` — one flat row per pricing record.
- `card_rows(res)` — one flat row per priced/enumerated card (expands the `cards[]`).
- `write_csv(path, rows, columns)` — RFC-4180 CSV, explicit column order.
- `render_html(rows, columns, *, title)` — one self-contained HTML page; clicking a `<th>` sorts by that
  column (numeric vs text detected per cell), no external assets/CDN.
- `build(records, outdir, *, ts=None)` — writes `listings_<ts>.csv`, `listings_<ts>.html`, `cards_<ts>.csv`;
  returns the paths.
- CLI: `--from-jsonl FILE` (default `data/finn/matches/pricing.jsonl`), `--outdir` (default
  `data/finn/tables`), `--ts`, `--json` (summary on stdout, progress on stderr, as in 0005).

## Out of scope (do NOT touch)

- Any pricing or network call (this stage is pure formatting of existing records).
- The Google Sheet / Apps Script path (`sheet/`) — optional, separate.
- Changing `finn_price.py` output shape.

## Success criteria (DEFINE THESE YOURSELF, before coding)

- [ ] Listings row: `finn_kode, heading, url, intent_rank, intent, asking_price_nok, market_value_nok,
      delta_nok, ratio, basis, cards_total, cards_priced, partial_coverage, listing_confidence, cache_hit, flags`.
- [ ] `ratio` is present and equals the stored `deal.ratio`; missing numbers render as empty CSV cells /
      `—` in HTML — never fabricated as 0.
- [ ] Cards table has exactly one row per enumerated card in every record (sum of `len(res["cards"])`).
- [ ] CSV round-trips (write → `csv.reader` → same header + row count).
- [ ] HTML is **self-contained** (no `http(s)://` asset refs) and contains a sort handler bound to header
      clicks.
- [ ] Listings sorted **best deal first** (`ratio` desc, missing last), deterministic tie-break.
- [ ] Nothing overwritten; outputs are timestamped and uniquely named.

## Test plan (write these tests FIRST — under `tests/`, stdlib, temp dir)

| Test | Input | Expected |
|---|---|---|
| `test_listing_row_fields` | one synthetic pricing record | all 16 keys present, ratio == deal.ratio |
| `test_cards_expansion` | record with 3 cards | 3 card rows, correct finn_kode/name/count |
| `test_missing_values_blank` | record with null market/ratio | CSV cell "" and HTML cell "—" |
| `test_sort_best_deals_first` | two listings, ratios 2.0 and 0.5 | 2.0 before 0.5; missing last |
| `test_csv_roundtrip` | rows → tmp CSV → read back | header + row count match |
| `test_html_self_contained_and_sortable` | rows → HTML string | has `<script>`, sort handler, no external URL |
| `test_cli_writes_timestamped_files` | `--from-jsonl` tmp + tmp outdir | rc 0, 3 files exist, names contain ts |

## Evidence to capture

- `uv run tests/test_finn_tables.py` output (count + OK).
- `uv run finn/finn_tables.py --from-jsonl data/finn/matches/pricing.jsonl --outdir <tmp>` then `type` the
  listings CSV head.
- Full-suite tally.

## Open questions / assumptions

- Input is `pricing.jsonl`; if a record predates 0005 fields it is tolerated (missing keys → blank).
- HTML sorting is client-side only (works from `file://`); no build step, no dependencies.
