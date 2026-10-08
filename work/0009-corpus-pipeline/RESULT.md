# 0009 — Archive→records join + fix the two integration bugs

**Status:** done
**Date:** 2026-10-08

## What was built

- **`finn/finn_corpus.py`** (new) — the missing join. Reads every
  `annonser/<kode>_<slug>/<kode>.json` view into one append-only
  `matches/corpus_<ts>.jsonl`. Bad JSON / orphans become `problems`, not crashes.
  `tests/test_finn_corpus.py` (4 tests). Real run: **107 records, 0 problems** →
  `data/finn/matches/corpus_2026-10-08-043400.jsonl`.
- **JSONL reader fix** — three readers used `str.splitlines()`, which splits on
  U+2028/U+2029/`\x85`/`\x0b`/`\x0c`; a real FINN `description_raw` contains U+2028, so
  one JSON object was torn in two. Changed to `.split("\n")` in
  `finn/finn_identify.py:176`, `finn/finn_report.py:62`, `finn/finn_ad.py:567`
  (`finn_price`/`finn_matcher` were already safe). `tests/test_jsonl_lines.py` (3 tests).
- **Matcher adapter fix** — `finn_matcher.listing_from_search` read only the *search*
  keys (`heading`/`price_amount`/…), so `--from-jsonl` over an archive corpus yielded
  `heading=None` for every ad (silent). Now falls back to the ad-view keys
  (`title`/`price_nok`/`url`/`location_text`). `tests/test_finn_matcher_adapters.py`
  (4 tests).

## Evidence (real runs)

- **Test-first, red→green:** `tests/test_jsonl_lines.py` went RED first (2 `ERROR`
  `JSONDecodeError` + 1 `FAIL`) then green; `tests/test_finn_matcher_adapters.py` went
  RED first (`AssertionError: None != 'Stort vintage salg…'`) then green.
- **Identify over the whole corpus:** `annotated 107 rows` (previously crashed on the
  JSONL bug) → `intent distribution: tier2-set=4, named-card=29, tier1-set=24, none=50`.
- **Matcher over the corpus (offline):** now parses real titles, e.g.
  `Morpeko 135/128 30th Celebration → name='Morpeko' num='135' set='30th Celebration'`
  (was `name=None` for all).
- **Live API pricing run** (`--from-jsonl corpus --max-calls 45`): produced real money
  numbers — one ad enumerated **50/57 cards priced**, market ≈ **49 483 kr** vs asking
  **100 kr** (ratio 494.83). Stopped loudly at the hourly floor
  (`STOP: hourly budget floor 5 reached`). API confirmed the rate move
  `48/100h → 5/100h`, `870/1000d`.
- **Coverage report** (`finn_report.py`): archived **107**, pricing `with_value=2`,
  `with_ratio=2`, cards **50/177 priced**.

## Notes / next

- The pipeline is now proven end-to-end on real data. Remaining work is **budget-bound**:
  a full pricing pass needs ~150+ uncached calls and the free plan allows 100/hour, so it
  is a ~2-hour drip, resumable across reboots (cache hits cost 0 calls; re-runs replay).
- To spread budget across *many* ads rather than one 57-card lot, use `--max-cards N`.
- `pricing.jsonl` / `matches.jsonl` are append-only, so record counts are cumulative
  across runs by design.
