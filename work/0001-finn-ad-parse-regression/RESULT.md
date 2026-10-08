# RESULT 0001 — Offline parse regression net for `finn/finn_ad.py`

- **Status:** done
- **Date:** 2026-10-08
- **Artifacts:** `tests/test_finn_ad_parse.py`, `tests/fixtures/finn_ad_475878513.html`

## What ran

```
uv run tests/test_finn_ad_parse.py
```

Observed (verbatim tail):

```
test_empty_page_is_failed ... ok
test_gallery_count_mismatch_warns ... ok
test_kode_disagreement_warns ... ok
test_breadcrumbs ... ok
test_description_has_card_list ... ok
test_gallery_and_images ... ok
test_identity_and_cross_check ... ok
test_last_modified ... ok
test_location ... ok
test_quality_full_no_warnings ... ok
test_similar_ads_present ... ok
test_title_status_price ... ok
test_parse_nok ... ok
test_parse_norwegian_datetime ... ok
----------------------------------------------------------------------
Ran 14 tests in 0.016s

OK
[fixture parse] kode='475878513' status='Inaktiv' price=100 gallery=25 images=25 quality='full' missing=[] warnings=[]
```

## Evidence vs success criteria

| Criterion | Result |
|---|---|
| stdlib `unittest`, no network | ✅ only `sys`/`unittest`/`pathlib` imported |
| identity + 4 kode candidates agree | ✅ `test_identity_and_cross_check` |
| title / status / trade / price | ✅ asserted `Inaktiv`, `Til salgs`, `100 kr`, `100` |
| location + coords | ✅ `1366 Lysaker`, pc `1366`, lat/lon to 6 dp |
| last_modified raw + ISO | ✅ `8.9.2026 kl. 18:44` → `2026-09-08T18:44:00` |
| gallery 25 == images 25, unique | ✅ |
| description `Liste over kort:` + card | ✅ `Venusaur` present, UI marker stripped |
| breadcrumbs / full / no missing / no warnings | ✅ |
| `_parse_nok`, `_parse_norwegian_datetime` | ✅ incl. NBSP thousands separator |
| can fail (negative tests) | ✅ empty page → `failed`; gallery mismatch → warning; kode disagreement → warning |

## Fixture provenance

Copied verbatim (guarded `if not exist`) from
`data/finn/annonser/475878513_stort-vintage-salg-av-pokemon-holo-rare-japansk-fastpris/raw/475878513_2026-10-02-163207.html`
(209 379 B, real server-saved capture). No file was modified or deleted.

## Assumptions

- The three saved raw captures for 475878513 are byte-identical in size; the newest was chosen as
  the fixture. Any of them is a faithful capture of the same ad.
- `data/` is treated as append-only truth and is **not** read by the test — the test depends only on
  the committed fixture, per `tests/README.md`.

## Residual / follow-ups (not blockers)

- This net covers `parse_ad()` (offline). `scrape_ad()` (fetch + image download) remains untested
  offline by design; it needs the network and belongs to the discovery/scrape items.

## Resume point

Item complete. Next: **0002** — wire `finn_search.py` to the `finn_searches.py` catalog
(`--search-set`) and verify discovery + registry delta (`new` / `still-active` / `gone`).
