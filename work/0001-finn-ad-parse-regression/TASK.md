# TASK 0001 — Offline parse regression net for `finn/finn_ad.py`

- **Status:** in-progress
- **Owner:** Zoo (code mode)
- **Output artifact(s):** `tests/test_finn_ad_parse.py`, `tests/fixtures/finn_ad_475878513.html`
- **Depends on:** none

## Goal (one sentence)

Lock the *currently correct* machine-read output of `finn_ad.parse_ad()` behind a committed,
offline test that parses a real saved FINN ad capture and asserts the verified field values.

## Why / context

`work/_index.md` states the highest-value first unit is a **regression net**, not a new feature:
there is no committed test suite, and every later pipeline change (identify, card-list parsing,
table build) assumes `finn_ad.py` keeps producing the same structured record. The parser already
works on a real capture: `data/finn/annonser/475878513_.../475878513.json` (checked 2026-10-06)
shows a clean, "full"-quality parse. This item freezes that behaviour so later work cannot
silently regress it.

Raw input is one saved page, copied verbatim into `tests/fixtures/` so the test needs no network:
`data/finn/annonser/475878513_.../raw/475878513_2026-10-02-163207.html` (209 379 B, real capture).

## In scope

- `finn_ad.parse_ad()` — the machine-read field set (spec §2.1) on a real capture.
- `finn_ad._parse_nok()` / `finn_ad._parse_norwegian_datetime()` — the two small value parsers.
- The parser's cross-check / quality behaviour: `parse_quality`, `missing_fields`, `warnings`
  (both the "full" happy path and a deliberately mismatching synthetic page).

## Out of scope (do NOT touch)

- `scrape_ad()` / network fetch / image download (needs the network — not offline-testable here).
- Any change to `finn/finn_ad.py` behaviour (this item is a test only; a red test is a finding).
- Search/discovery, matcher, pricing, tables (separate work items).

## Success criteria (DEFINE THESE YOURSELF, before coding)

- [ ] `uv run tests/test_finn_ad_parse.py` passes, using **stdlib `unittest` only**, no network.
- [ ] It asserts identity + all 4 kode cross-check candidates agree on `475878513`.
- [ ] It asserts `title`, `status` (`Inaktiv`), `trade_type`, `price_label`, `price_nok`.
- [ ] It asserts location (`location_text`, `postal_code`, `lat`, `lon`).
- [ ] It asserts `last_modified_raw` and the ISO `last_modified`.
- [ ] It asserts `gallery_count` == 25 == `image_count_from_html` == unique `image_uuids`.
- [ ] It asserts `description_raw` contains the `Liste over kort:` block and a known card name.
- [ ] It asserts `breadcrumbs`, `parse_quality == "full"`, empty `missing_fields`, empty `warnings`.
- [ ] It includes unit checks for `_parse_nok` and `_parse_norwegian_datetime`.
- [ ] It **can fail**: a negative test proves an empty page parses to `failed`, and a synthetic page
      with a gallery-count/image mismatch produces a warning.

## Test plan (write these tests FIRST — under `tests/`)

| Test | Input | Expected |
|---|---|---|
| `test_identity_and_cross_check` | fixture | `finn_kode=="475878513"`, 4 candidates all equal it |
| `test_title_status_price` | fixture | title/`Inaktiv`/`Til salgs`/`100 kr`/`100` |
| `test_location` | fixture | `1366 Lysaker`, pc `1366`, lat/lon ≈ verified |
| `test_last_modified` | fixture | `8.9.2026 kl. 18:44` → `2026-09-08T18:44:00` |
| `test_gallery_and_images` | fixture | 25 == 25 == len(uuids), all unique |
| `test_description_has_card_list` | fixture | contains `Liste over kort:` and `Venusaur` |
| `test_breadcrumbs` | fixture | the 4-level Torget trail |
| `test_quality_full_no_warnings` | fixture | `full`, no missing, no warnings |
| `test_parse_nok` | `"100 kr"`,`"1 200 kr"`,`"1.200,-"`,`None` | `100`,`1200`,`1200`,`None` |
| `test_parse_norwegian_datetime` | `"8.9.2026","18:44"` | `2026-09-08T18:44:00` |
| `test_empty_page_is_failed` | `"<html></html>"` | `failed`, finn_kode None, missing has kode+title |
| `test_gallery_count_mismatch_warns` | synthetic HTML | a warning mentioning `gallery_count` |

## Evidence to capture

- `uv run tests/test_finn_ad_parse.py` output: test count, OK/FAIL, and the printed parse summary.

## Open questions / assumptions

- The 3 raw captures for 475878513 are byte-identical in size; the newest (`...163207`) was copied
  as the fixture. Assumption: any of them is a faithful capture of the same ad.
- `tests/fixtures/` did not exist; created it. Fixture write is guarded (`if not exist`) so it can
  never overwrite an existing file.
- No PEP 723 `# /// script` block is hand-written (rules forbid hand-editing dependency blocks);
  the test is stdlib-only so `uv run` needs no metadata.
