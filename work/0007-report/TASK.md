# TASK 0007 — Program coverage report

- **Status:** done
- **Owner:** Zoo (code mode)
- **Output artifact(s):** `finn/finn_report.py`, `tests/test_finn_report.py`
- **Depends on:** 0002–0006 artifacts (`data/finn/registry`, `searches/`, `matches/`, `annonser/`), `finnlib`,
  `finn_identify`
- **Reuses (does NOT re-hard-code):** `finnlib.DATA_FINN/ensure_dir/unique_path/ts_now`, `finn_identify.identify_ad`

## Goal (one sentence)

Read the append-only artifacts the pipeline has produced and emit an honest **coverage report** — how many
ads were discovered, archived, ranked, matched and priced, and where the gaps are — so the program's
finished state is *demonstrated*, not asserted.

## Why / context

`SCRAPING_PROMPT.md`'s finished state is "proven by committed tests and a coverage report". Items 0001–0006
built the machinery; nothing yet counts what actually flowed through it. This item is that accounting —
deterministic, offline, stdlib-only.

## In scope

- `count_registry(path)` → `{koder, first_seen, last_seen}` from `registry/pokemon-kort.json`.
- `count_runs(searches_dir)` → `{runs, pages, docs}` summed from each `*/run.json` `totals`.
- `count_matches(path)` → `{records, matched}` from `matches/matches.jsonl` (`matched` = `best` non-null).
- `count_pricing(path)` → `{records, with_value, with_ratio, basis, cards_total, cards_priced}` from
  `matches/pricing.jsonl`.
- `count_archive(annonser_dir)` → `{ads}` (one per archived-ad directory).
- `intent_distribution(ads)` → counts per `finn_identify` intent label, **deduped by `finn_kode`**.
- `coverage(...)` — compose all of the above into one dict.
- `render_markdown(cov)` — a short, readable report.
- `build(cov, outdir, *, ts=None)` — writes `coverage_<ts>.json` + `coverage_<ts>.md`.
- CLI: `--registry`, `--searches-dir`, `--matches`, `--pricing`, `--annonser`, `--outdir`
  (default `data/finn/reports`), `--ts`, `--json` (stdout JSON, stderr progress).

## Out of scope (do NOT touch)

- No scraping, no pricing, no network at all (pure accounting of existing artifacts).
- No Google Sheet.

## Success criteria (DEFINE THESE YOURSELF, before coding)

- [ ] Counts are computed from real files, never hard-coded; a missing artifact yields zeros + a note
      (not an exception).
- [ ] `intent_distribution` dedupes by `finn_kode` and totals match the number of unique kodes.
- [ ] `with_value`/`with_ratio` count only records whose `deal.market_value_nok`/`deal.ratio` are non-null.
- [ ] Markdown contains a section per stage (discovery / archive / identify / match / pricing) with the
      real numbers; nothing is claimed that the counts don't show.
- [ ] Output JSON + Markdown are timestamped and uniquely named (never overwritten).
- [ ] The report surfaces gaps loudly (e.g. `ads_archived < koder`, `cards_priced == 0`).

## Test plan (write these tests FIRST — under `tests/`, stdlib, temp dir)

| Test | Input | Expected |
|---|---|---|
| `test_count_registry` | 2-kode registry JSON | `koder==2`, `first_seen`/`last_seen` = min/max |
| `test_count_runs` | two `run.json` | pages/docs summed; runs==2 |
| `test_count_matches` | 2 records, 1 with `best` | `records==2`, `matched==1` |
| `test_count_pricing` | 2 records | `with_value==1`, `with_ratio==1`, basis tally, cards sums |
| `test_count_archive` | 2 ad dirs | `ads==2` |
| `test_intent_distribution_dedupes` | 2 ads, one duplicated kode | total == unique kodes |
| `test_missing_artifact_is_zero` | non-existent paths | zeros, no crash, note emitted |
| `test_cli_writes_files` | tmp fixtures + tmp outdir | rc 0, `.json` + `.md` exist, names contain ts |

## Evidence to capture

- `uv run tests/test_finn_report.py` output.
- `uv run finn/finn_report.py` against the real `data/finn/` and the rendered Markdown, `type`d.
- Full-suite tally.

## Open questions / assumptions

- "Interesting ad" is proxied by the `finn_identify` intent rank (>0); the report shows the full
  distribution so the proxy is visible.
- Only the latest search run's `all_ads.jsonl` (if any) is read for the intent distribution.
