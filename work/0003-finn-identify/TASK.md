# TASK 0003 — Build `finn/finn_identify.py` (rank an ad by Marius' intent)

- **Status:** in-progress
- **Owner:** Zoo (code mode)
- **Output artifact(s):** `finn/finn_identify.py`, `tests/test_finn_identify.py`
- **Depends on:** 0001 (fixture), 0002 (catalog)

## Goal (one sentence)

Given an ad's text (title/heading + description), decide **which interesting set(s) and named card(s)**
it is, using `finn_searches.SETS`/`CARDS`, and return a priority rank so listings can be ordered by how
much Marius wants them.

## Why / context

`SCRAPING_PROMPT.md` §4 lists `finn/finn_identify.py` as **referenced but missing** ("reuses `SETS`/`CARDS`
to work out which *interesting* set/card an ad is. Needed to rank listings by Marius' intent"). §5 stage 3
and §9 (priority: Tier-1 sets → named cards → Tier-2 sets) depend on it. Without it the pipeline cannot
tell a Skyridge gem from generic bulk.

Reuses the catalog (`SETS`, `CARDS`) — no new hard-coded lists. Real input for the integration test is the
committed capture `tests/fixtures/finn_ad_475878513.html`, whose description enumerates Gym Heroes / Gym
Challenge / Neo Destiny / Neo Revelation and cards Mew / MewTwo / Gengar / Jolteon.

## In scope

- `normalize()` — case/diacritic/punctuation folding ("Pokémon"→"pokemon", "Ho-Oh"→"ho oh").
- `find_set_matches()` / `find_card_matches()` — word-boundary alias matching against `SETS`/`CARDS`.
- `intent_rank()` — 1 Tier-1 set, 2 named card, 3 Tier-2 set, 0 none.
- `identify(text)`, `identify_ad(record)`, `annotate(row)`.
- CLI: `--title`/`--text`/`--description-file`, `--json`, and `--from-jsonl FILE [--out FILE]`.

## Out of scope (do NOT touch)

- `finn_searches.py` catalog content (this item *consumes* it; extending aliases is a later item).
- PokeWallet matching/pricing (`finn_matcher.py`) and the table build.
- Scraping/fetch.

## Success criteria (DEFINE THESE YOURSELF, before coding)

- [ ] `normalize` folds case, strips diacritics and punctuation, collapses whitespace.
- [ ] Alias matching is **word-boundary** safe: "mew" must not match inside "mewtwo".
- [ ] Matches carry `name`, `tier`, `year`, `alias`, `kind`; sets and cards are de-duplicated by name.
- [ ] `intent_rank` implements the documented priority and returns 0 when nothing matches.
- [ ] On the real capture, identify returns exactly the sets/cards the description enumerates.
- [ ] `annotate(row)` adds an `identify` object without mutating the input row.
- [ ] CLI single-input and `--from-jsonl` both run and print real counts.

## Test plan (write these tests FIRST — under `tests/`)

| Test | Input | Expected |
|---|---|---|
| `test_normalize_basic` | `"Pokémon"`,`"MewTwo"`,`"  Gym  Heroes \n ✨"`,`"Ho-Oh"` | `pokemon`,`mewtwo`,`gym heroes`,`ho oh` |
| `test_finds_sets_with_tiers` | "Gym Heroes; Gym Challenge, Neo Destiny, Neo Revelation, 1st edition" | 4 sets w/ tiers 1/1/2/1 + Base Set 1st Ed (tier 2) |
| `test_word_boundary` | "Mew MewTwo Gengar Jolteon" | exactly {Mew,Mewtwo,Gengar,Jolteon} |
| `test_no_substring_false_positive` | "mewtwo only" | exactly {Mewtwo} (no Mew) |
| `test_priority` | tier-1 set vs card vs tier-2 set vs none | ranks 1 / 2 / 3 / 0 |
| `test_identify_real_ad` | fixture via `finn_ad.parse_ad` | rank 1, sets ⊇ {Gym Heroes,Gym Challenge,Neo Revelation}, cards ⊇ {Mew,Mewtwo,Gengar,Jolteon} |
| `test_annotate_rows` | headings w/ and w/o matches | `identify` added; rank 1 for Lugia/Neo Genesis; 0 for none |
| `test_cli_json` | `--title "Skyridge Umbreon" --json` | rc 0, JSON with Umbreon + Skyridge |

## Evidence to capture

- `uv run tests/test_finn_identify.py` output (count + OK).
- `uv run finn/finn_identify.py --title "..." --json` real JSON.
- `uv run finn/finn_identify.py --from-jsonl <real run all_ads.jsonl>` → rank distribution counts.

## Open questions / assumptions

- "Interesting" = matched a `SETS` entry or a `CARDS` entry; broad-phrase-only ads rank 0.
- Sets and cards are matched against the **whole** ad text (title + description + breadcrumbs), because the
  real examples list the sets/cards in the description, not the heading.
- `--from-jsonl` writes to a fresh `unique_path` (never overwrites); default out is stdout.
