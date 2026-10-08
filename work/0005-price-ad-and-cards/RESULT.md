# RESULT 0005 — Price an ad, and each card it enumerates

- **Status:** done
- **Owner:** Zoo (code mode)
- **Artifacts:** `finn/finn_price.py` (new), `tests/test_finn_price.py` (new)
- **Depends on:** 0003 (`finn_identify`), 0004 (`finn_cards`), `finn_matcher` (reused as-is), `pwlib` — satisfied.
- **Reuses (no second API path):** `finn_matcher.parse_heading` / `plan_queries` / `resolve_queries` /
  `score_candidate` / `_native_price` / `load_cache` / `FX_DEFAULTS` / `match_listing`, plus `pwlib.prices`.

## Deliverable

[`finn/finn_price.py`](../finn/finn_price.py) attaches a **pricing** block to a parsed ad that puts a
PokeWallet market value (NOK, `estimated=true`) next to the seller's asking price — for the listing as a
whole **and for each enumerated card** — cache-first and budget-aware.

Public surface:

- [`confidence_of()`](../finn/finn_price.py:70) — `high` / `medium` / `low` / `none` from name+number+set
  signals (conservative; a set the ad named but the candidate does **not** match is a red flag → `low`).
- [`deal_math()`](../finn/finn_price.py:95) — `ratio = market / asking` (higher = better deal),
  `delta_nok = asking - market`; both `None` when a side is missing (and no divide-by-zero).
- [`price_ad()`](../finn/finn_price.py:247) — listing-level value (title → one card) + per-card value for
  every `finn_cards` row, with the ad's `finn_identify` set matches sharpening the per-card queries.
- CLI: `--heading`, `--ad-json`, `--from-jsonl`, `--offline`, `--cache-file`, `--cache-hours`, `--max-cards`,
  `--max-queries`, `--max-calls`, `--price-low`, `--fx-usd`, `--fx-eur`, `--outdir`, `--json`.
- Append-only outputs: `data/finn/matches/pricing.jsonl` + a timestamped `pricing_<ts>.json`.

## Success criteria — met

- [x] Offline + seeded cache ⇒ a value with **0 API calls** (`test_offline_uses_cache_no_calls`); empty
      cache ⇒ `null` values, **no crash**, 0 calls (`test_empty_cache_is_unpriced`).
- [x] Name-exact but **named set not matched** ⇒ `confidence="low"`, **not** priced by default
      (`test_low_confidence_name_only_skipped`); priced with `--price-low` (`test_price_low_opt_in`).
- [x] Enumerated cards: rows carry `name,count,variants,unit_market_value_nok,market_value_nok,score,
      confidence,flags`; the total sums **only** valued cards; `card_coverage` + `partial_card_coverage`
      reported (`test_card_list_partial_coverage`).
- [x] `deal.ratio == market/asking`; `basis ∈ {card_list_sum, listing_best, none}` (`test_ratio_math`,
      `test_listing_best_basis`).
- [x] `count` multiplier applied (`4x Pikachu` ⇒ 4 × unit value) (`test_count_multiplier`).
- [x] Nothing overwritten; output appended + timestamped (CLI asserts `pricing.jsonl` written).

## Design notes / decisions

- **No second API path.** Both the listing-level and per-card lookups go through `finn_matcher.resolve_queries`
  (cache-aware, budget-capped) and therefore share the same append-only cache. Live calls are opt-in.
- **`--max-calls`** (default 25) is an added global cap so a 57-card ad in live mode cannot burn the plan;
  when hit, pricing stops and a `flags[]` entry says so — never silent.
- **Honest coverage.** `card_coverage.total` is the **full** parsed list even when `--max-cards` truncates
  what is priced, so a partial sum is never presented as complete (`partial_card_coverage=true`).
- **`--json` writes machine JSON to stdout and progress to stderr**, so output stays parseable while nothing
  is hidden from the terminal.

## Evidence

`uv run tests/test_finn_price.py` → **11 tests, OK** (10 planned + `Confidence.test_levels`).

Full suite (regression check): `test_finn_ad_parse` 14 OK · `test_finn_search_catalog` 10 OK ·
`test_finn_identify` 10 OK · `test_finn_cards` 12 OK · `test_finn_price` 11 OK → **57 tests OK**.

Real cached value, **0 API calls** (`uv run finn/finn_price.py --heading "Psychic Energy Base Set 101"
--finn-price 9 --offline --cache-hours 9999`):

```
[1/1] 'Psychic Energy Base Set 101'
      cards: 0/0 priced  partial=False
      deal: basis=listing_best asking=9.0 market=7 ratio=0.7778 delta=2
      calls=0 cache=True
```

Real ad, offline, 57 enumerated cards (`uv run finn/finn_price.py --ad-json
data/finn/annonser/475878513_.../475878513.json --offline`):

```
[1/1] 'Stort vintage salg av Pokemon Holo/Rare/Japansk (Fastpris)'
      cards: 0/57 priced  partial=True
      deal: basis=none asking=100 market=None ratio=None delta=None
      calls=0 cache=False
```

## Findings (honest, not suppressed)

1. **Cache key vs parser drift.** The one committed cache entry is keyed `psychic energy base set 101`
   (written by an earlier parser). The current `finn_matcher` plans `Psychic Energy 101` / `Base Set 101`
   for the heading `"Psychic Energy #101 Base Set (1999)"`, so that heading **misses** the cache (0 calls,
   no value). Using the literal heading `"Psychic Energy Base Set 101"` reproduces the cached query and
   yields the real value above. The unit test (`test_listing_best_basis`) pins the mechanism with a seeded
   cache; this note records that the *committed* cache is not addressable by the current planner.
2. **Stale-cache window.** The committed cache is >24 h old, so the default `--cache-hours 24` treats it as
   stale. Evidence above uses `--cache-hours 9999` to exercise the cached path; `keep`/raise the default
   if you want old snapshots reused.
3. **Card prices currently 0/57** for the real ad simply because no per-card query has been cached yet
   (the cache holds a single energy-card query). Running live (or after a live crawl populates the cache)
   is what fills these; the machinery and honest `partial_card_coverage` reporting are in place.
4. **Test correction (recorded as such):** `test_listing_best_basis` initially seeded the wrong query key
   (`"Psychic Energy 101"`); the engine plans `"Psychic Energy Base Set 101"` when it has no set index.
   The seed was corrected to the engine's real query — the expectation (`basis=listing_best`) was right.
5. **Variants are captured but not used to pick a price sub-type yet** (`holo` vs `reverse holo` can differ
   materially). Left for a follow-up; noted rather than guessed.
