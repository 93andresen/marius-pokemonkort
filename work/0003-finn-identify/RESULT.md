# RESULT 0003 — Build `finn/finn_identify.py` (rank an ad by Marius' intent)

- **Status:** done
- **Date:** 2026-10-08
- **Artifacts:** `finn/finn_identify.py`, `tests/test_finn_identify.py`

## What ran

### 1. Tests (offline)

```
uv run tests/test_finn_identify.py
→ Ran 10 tests ... OK
  [real ad] rank=1 sets=['Base Set','Gym Challenge','Gym Heroes','Neo Revelation','Neo Destiny']
            cards=['Gengar','Jolteon','Mew','Mewtwo']
  [sets] matched ['Base Set (1st Edition / Shadowless)','Gym Challenge','Gym Heroes','Neo Destiny','Neo Revelation']
```

### 2. Real batch over the live discovery run (53 real ads)

```
uv run finn/finn_identify.py --from-jsonl data/finn/searches/2026-10-08-025742/all_ads.jsonl
→ intent distribution: tier2-set=3, named-card=17, tier1-set=7, none=26
```

Spot-checks from the real output: `"Base Set, Base Set 2" + Pikachu → rank 1`; `"Team Rocket" + "EX Team
Rocket Returns" → rank 1`; `"Skyridge" → rank 3`; `Mightyena → rank 2`; plain bulk → rank 0.

## Evidence vs success criteria

| Criterion | Result |
|---|---|
| normalize folds case/diacritics/punctuation | ✅ `test_normalize_basic` (incl. Ho-Oh→"ho oh") |
| word-boundary safe | ✅ `test_no_substring_false_positive` ("mewtwo only" → {Mewtwo}) |
| matches carry name/tier/year/alias/kind, de-duped | ✅ `_find` returns one row per name |
| `intent_rank` 1/2/3/0 | ✅ `test_priority`, `test_tier1_beats_card` |
| real capture → exact sets/cards | ✅ `test_identify_real_ad` |
| `annotate` adds `identify`, no mutation | ✅ `test_annotate_does_not_mutate_input` |
| CLI single + `--from-jsonl` run, print counts | ✅ both run above |

## Findings / corrections (honest record)

- A test I wrote asserted `intent_rank("Skyridge Umbreon") == 3`. It is actually **2**: a *named card*
  (Umbreon, rank 2) outranks a *Tier-2 set* (Skyridge, rank 3) per the documented priority (TASK + brief §9).
  The code is correct; the assertion was wrong, so I corrected the assertion (with a comment) rather than the
  behaviour. This is a corrected expectation, not a weakened test — the priority contract is still asserted.
- Real-word note: on page 1 of "pokemon kort", 26/53 ads match nothing interesting ("none") — expected for a
  broad page-1 sample dominated by bulk lots. This is why identification (not the raw query) drives priority.

## Design decisions / assumptions

- Interesting = matched a `SETS` or `CARDS` entry. Broad-phrase-only ads → rank 0.
- Match against the **whole** ad text (title/heading + `description_raw` + breadcrumbs); the real examples
  list sets/cards in the description, not the heading.
- `CARDS` have no tier in the catalog; the module assigns them `intent_rank` 2 in `intent_rank()`. Their
  per-match `tier` stays `null` (catalog truth) — the rank mapping lives in `intent_rank`, not the data.
- `--from-jsonl --out` writes to a fresh `fl.unique_path` (never overwrites); without `--out` it prints to stdout.

## Residual / follow-ups (not blockers)

- `identify` currently reports the *first* matching alias per item; multiple aliases are not all recorded.
  Fine for ranking; can be enriched later if needed.
- Typo/variant alias expansion (`SCRAPING_PROMPT.md` §3.2) is a separate catalog item.

## Resume point

Item complete. Next: **0004** — card-list structuring from `description_raw` (parse `Liste over kort:` blocks,
provenance, title-vs-description count reconciliation).
