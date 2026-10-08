# 0009 — Archive→records join + fix the two integration bugs

**Status:** done
**Date:** 2026-10-08

## Goal

Make the archived ads actually flow through the downstream pipeline
(identify → match → price). The stages each consume a JSONL of records, but nothing
joined the per-ad archive into one file — and two latent bugs made the join unusable.

## Success criteria

1. A reusable join: `finn/finn_corpus.py` reads every
   `data/finn/annonser/<kode>_<slug>/<kode>.json` view into one append-only
   `data/finn/matches/corpus_<ts>.jsonl`.
2. No silent data loss: JSONL readers must not split a record on Unicode line
   separators (U+2028/U+2029/…) — a real FINN description contains them.
3. The matcher's `--from-jsonl` must not silently null a heading when pointed at the
   archive (ad-view) shape.
4. Tests written **first** (red), then green; whole suite green.

## Test plan

- `tests/test_finn_corpus.py` — join reads views sorted, flags orphans, tolerates bad
  JSON, CLI writes a timestamped corpus.
- `tests/test_jsonl_lines.py` — a record containing every `str.splitlines()` boundary
  char survives `_load_rows` / `_read_jsonl` / `_load_kodes_from` intact.
- `tests/test_finn_matcher_adapters.py` — `listing_from_search` reads both the search
  shape and the archive ad-view shape.
