# RESULT 0006 — Build the sortable listings + cards tables

- **Status:** done
- **Owner:** Zoo (code mode)
- **Artifacts:** `finn/finn_tables.py` (new), `tests/test_finn_tables.py` (new)
- **Depends on:** 0005 (`finn_price.py` → `data/finn/matches/pricing.jsonl`), `finnlib` — satisfied.
- **Reuses (no new deps):** `finnlib.ensure_dir/unique_path/ts_now/DATA_FINN`, stdlib `csv`/`html`/`json`.

## Deliverable

[`finn/finn_tables.py`](../finn/finn_tables.py) is the program's **headline output**: it turns the
append-only `pricing.jsonl` records into two human-facing views under `data/finn/tables/`:

- a **listings table** — one row per ad, **best deal first**, with the deal ratio
  (`market_value_nok / asking_price_nok`) next to the seller's asking price;
- a **cards table** — one row per enumerated card across all ads.

Both are emitted as RFC-4180 **CSV**; the listings are *also* emitted as a single
**self-contained HTML** page whose header cells sort on click (numeric vs text detected per column,
works from `file://`, no external assets/CDN).

Public surface:

- [`listing_row()`](../finn/finn_tables.py:76) — flatten one pricing record into the 16-column row.
- [`card_rows()`](../finn/finn_tables.py:104) — expand one record's `cards[]` into flat card rows.
- [`sort_listings()`](../finn/finn_tables.py:133) — `ratio` desc, missing last, deterministic tie-break.
- [`write_csv()`](../finn/finn_tables.py:186) — RFC-4180 CSV, explicit header/column order.
- [`render_html()`](../finn/finn_tables.py:250) — one self-contained, client-side-sortable page.
- [`build()`](../finn/finn_tables.py:301) — writes `listings_<ts>.csv|html` + `cards_<ts>.csv`.
- CLI: `--from-jsonl` (default `data/finn/matches/pricing.jsonl`), `--outdir` (default
  `data/finn/tables`), `--ts`, `--json` (summary on stdout, progress on stderr).

## Success criteria — met

- [x] Listings row has exactly the 16 columns
      `finn_kode, heading, url, intent_rank, intent, asking_price_nok, market_value_nok, delta_nok,
      ratio, basis, cards_total, cards_priced, partial_coverage, listing_confidence, cache_hit, flags`
      (`test_listing_row_fields`).
- [x] `ratio` equals the stored `deal.ratio`; missing numbers render as **empty CSV cells** / **`—` in
      HTML**, never fabricated as `0` (`test_missing_values_blank`, `test_missing_values_dash_in_html`).
- [x] Cards table has **exactly one row per enumerated card** (sum of `len(res["cards"])`)
      (`test_cards_expansion`, `test_build_card_count_matches_sum`).
- [x] CSV **round-trips** (write → `csv.reader` → identical header + row count) (`test_csv_roundtrip`).
- [x] HTML is **self-contained** (no `http(s)://`, no `<script src`, no `<link`) and contains an inline
      sort handler bound to header clicks (`test_html_self_contained_and_sortable`).
- [x] Listings sorted **best deal first** (`ratio` desc, missing last) with a deterministic tie-break
      (`test_sort_best_deals_first`, `test_sort_is_deterministic_tiebreak`).
- [x] Nothing overwritten; outputs are timestamped and uniquely named (`unique_path`) — the CLI test
      asserts the three exact `*_2026-01-02-030405.*` filenames (`test_cli_writes_timestamped_files`).

## Design notes / decisions

- **Pure formatting stage.** No network, no cache, no API — it only reads records that 0005 already
  produced, so it is deterministic and cheap to re-run.
- **Missing ≠ zero.** `None` → blank CSV cell, `—` HTML cell; the HTML sorter treats `—`/blank as
  `null` so they always sort last regardless of direction. This keeps "unknown" visually distinct from a
  real `0`.
- **Numeric column detection.** A column sorts numerically iff *every* present cell is a number
  (`int`/`float`, excluding `bool`); otherwise it sorts case-insensitively as text. The choice is baked
  into each `<th data-type>` at render time so no runtime type-sniffing is needed.
- **Self-contained by construction.** Styles and the sort script are inlined; the page has no external
  references, so it opens correctly straight from disk.

## Evidence

`uv run tests/test_finn_tables.py` → **11 tests, OK** (the 7 planned + `test_flags_joined`,
`test_build_card_count_matches_sum`, `test_missing_values_dash_in_html`, `test_sort_is_deterministic_tiebreak`).

Full suite (regression check): `test_finn_ad_parse` 14 OK · `test_finn_search_catalog` 10 OK ·
`test_finn_identify` 10 OK · `test_finn_cards` 12 OK · `test_finn_price` 11 OK · `test_finn_tables` 11 OK
→ **68 tests OK**.

Real run (`uv run finn/finn_tables.py --from-jsonl data/finn/matches/pricing.jsonl`):

```
FINN tables  |  4 record(s)  |  ts=2026-10-08-031255
  listings_csv  -> data\finn\tables\listings_2026-10-08-031255.csv  (4 rows)
  listings_html -> data\finn\tables\listings_2026-10-08-031255.html
  cards_csv     -> data\finn\tables\cards_2026-10-08-031255.csv  (57 rows)
```

`data/finn/tables/listings_2026-10-08-031255.csv` (head) — note the deal row sorts first, missing
values are blank, and the 57-card ad carries its partial-coverage flag:

```
finn_kode,heading,url,intent_rank,intent,asking_price_nok,market_value_nok,delta_nok,ratio,basis,cards_total,cards_priced,partial_coverage,listing_confidence,cache_hit,flags
,Psychic Energy Base Set 101,,1,tier1-set,9.0,7,2,0.7778,listing_best,0,0,false,high,true,
,Psychic Energy #101 Base Set (1999),,1,tier1-set,9.0,,,,none,0,0,false,none,false,
,Psychic Energy Base Set 101,,1,tier1-set,9.0,,,,none,0,0,false,none,false,
475878513,Stort vintage salg av Pokemon Holo/Rare/Japansk (Fastpris),,1,tier1-set,100,,,,none,57,0,true,none,false,card list only partially priced (0/57)
```

HTML head confirms inline script + per-column sort binding and no external assets:

```
<th data-col="3" data-type="number" onclick="sortTable(this)">intent_rank</th>
```

## Findings (honest, not suppressed)

1. **The caught corruption artifact in 0005.** While re-reading `finn_price.py` for this item I found a
   leftover dead-code artifact on the `fx` line (`... if False else ...` referencing a non-existent
   `args.fx_euro`). It was harmless at runtime (the `False` branch never evaluated) but wrong; it is now
   replaced with the single correct `fx = {"USD": ..., "EUR": args.fx_eur}`. Recorded so the 0005 file is
   not assumed pristine.
2. **Rows 3–4 are the same heading with different cache states.** In the real output the two
   `"Psychic Energy Base Set 101"` rows differ only in `cache_hit`; both show `basis=none` because the
   committed cache is >24 h stale (see 0005 finding #2). The table faithfully reflects whatever price
   records exist — it does not re-run pricing.
3. **57 card rows are all unpriced.** The cards table therefore renders 57 rows with blank market
   values; this is the honest picture of the current cache, not a formatting bug (0005 finding #3).
4. **CSV is the machine artifact; HTML is the human artifact.** The cards table has no HTML twin by
   design (the brief specifies HTML for listings). If a sortable cards view is wanted, it is a small
   follow-up (`render_html` already generalises to any rows+columns).
