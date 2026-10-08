# TASK 0005 — Price a parsed ad, and each card it enumerates

- **Status:** in-progress
- **Owner:** Zoo (code mode)
- **Output artifact(s):** `finn/finn_price.py`, `tests/test_finn_price.py`
- **Depends on:** 0003 (`finn_identify`), 0004 (`finn_cards`), `finn_matcher` (existing), `pwlib`
- **Reuses (does NOT re-hard-code):** `finn_matcher.parse_heading/plan_queries/resolve_queries/
  score_candidate/_native_price/load_cache/FX_DEFAULTS`, `pwlib.prices`, `finnlib`

## Goal (one sentence)

Given a parsed ad (optionally already identified + card-structured), attach a **pricing** block that puts a
trustworthy PokeWallet market value (NOK, `estimated=true`) next to the seller's asking price — for the
listing as a whole and **for each enumerated card** — cache-first and budget-aware, so the best deals surface.

## Why / context

`SCRAPING_PROMPT.md` requires the final table to show `market_value_nok / asking_price_nok` (a deal ratio).
The existing `finn_matcher.py` prices **one heading → one card**; it cannot price an ad whose description
enumerates dozens of cards (the real capture lists 57). This item adds the missing per-ad / per-card layer on
top of the *same* cached, budget-capped query engine — never a second, unbudgeted path to the API.

## In scope

- `confidence_of(scored)` — high / medium / low / none, from name+set+price signals (loud, conservative).
- `price_ad(record, *, client, index, cache, cache_hours, offline, fx, max_queries, max_cards, price_low)`.
- Listing-level value from the ad title (`parse_heading`).
- Per-card value for every row of `finn_cards.parse_card_list`, using the ad's `finn_identify` set matches to
  sharpen queries (try each set hint, then the bare name).
- `deal` block: `{market_value_nok, asking_price_nok, delta_nok, ratio, basis}`.
- Coverage is explicit: priced/total cards + a `partial_card_coverage` flag — a partial sum is never passed
  off as complete.
- CLI: `--ad-json`, `--from-jsonl FILE [--out]`, `--offline`, `--cache-file`, `--cache-hours`,
  `--max-cards`, `--max-queries`, `--price-low`, `--fx-usd`, `--fx-eur`, `--outdir`, `--json`.
- Append-only outputs: `data/finn/matches/pricing.jsonl` + a timestamped `pricing_<ts>.json`.

## Out of scope (do NOT touch)

- Changing `finn_matcher.py`'s behaviour (call its functions as-is).
- The table/sheet writer (item 0006).
- Any live scrape. Live calls are opt-in (default on only without `--offline`); evidence uses the cache.

## Success criteria (DEFINE THESE YOURSELF, before coding)

- [ ] Offline + a seeded cache ⇒ a value with **0 API calls**; no cache ⇒ `null` values, **no crash**, 0 calls.
- [ ] A candidate that matches by name but not by set ⇒ `confidence="low"`, **no** value (unless `--price-low`).
- [ ] Enumerated cards: per-card rows carry `name,count,variants,unit_market_value_nok,market_value_nok,
      score,confidence,flags`; total sums **only** valued cards; coverage + `partial_card_coverage` reported.
- [ ] `deal.ratio == market_value_nok / asking_price_nok`; `basis` ∈ {card_list_sum, listing_best, none}.
- [ ] Multiplier `count` is applied (`4x Pikachu` ⇒ 4 × unit value).
- [ ] Nothing is overwritten; output is appended and timestamped.

## Test plan (write these tests FIRST — under `tests/`, offline, seeded cache)

| Test | Input | Expected |
|---|---|---|
| `test_ratio_math` | market 200, asking 100 | ratio 2.0, delta -100 |
| `test_ratio_none_when_no_asking` | asking None | ratio None, no crash |
| `test_offline_uses_cache_no_calls` | cache has "Venusaur Base Set" | value present, calls_spent 0, cache_hit True |
| `test_empty_cache_is_unpriced` | empty cache | card priced False, market value None, 0 calls |
| `test_low_confidence_name_only_skipped` | cache has name-only (wrong set) match | confidence low, value None by default |
| `test_price_low_opt_in` | same, `price_low=True` | value assigned |
| `test_card_list_partial_coverage` | 3 cards, 1 cached | priced 1/3, `partial_card_coverage` flag, sum=that card |
| `test_count_multiplier` | "4x Pikachu" cached | market_value == 4 × unit |
| `test_listing_best_basis` | single-card title cached | basis listing_best |
| `test_cli_offline_json` | `--ad-json` + `--offline --cache-file` | rc 0, JSON has `deal` + `cards` |

## Evidence to capture

- `uv run tests/test_finn_price.py` output (count + OK).
- `uv run finn/finn_price.py --ad-json data/finn/annonser/475878513_.../475878513.json --offline` (real cache).
- `uv run finn/finn_price.py --heading "Psychic Energy #101 Base Set (1999)" --finn-price 9 --offline`
  (cached query exists → real value, 0 calls).

## Open questions / assumptions

- No number ⇒ matching leans on **name + set**; a name-only hit is `low` and unpriced by default (the
  Mew/Mewtwo trap). Conservative by design.
- One ad can span many sets; per-card queries try each identified set, then the bare name.
- FX is an explicit, labelled estimate (`estimated=true`), overridable via `--fx-*`.
