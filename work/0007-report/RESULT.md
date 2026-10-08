# RESULT 0007 — Program coverage report

- **Status:** done
- **Owner:** Zoo (code mode)
- **Artifacts:** `finn/finn_report.py` (new), `tests/test_finn_report.py` (new)
- **Depends on:** 0002–0006 artifacts — satisfied.
- **Reuses (no new deps):** `finnlib.DATA_FINN/ensure_dir/unique_path/ts_now/iso_now`, `finn_identify.identify_ad`.

## Deliverable

[`finn/finn_report.py`](../finn/finn_report.py) is the program's **accounting layer**. It reads the
append-only artifacts the earlier stages wrote and emits an honest coverage report (machine JSON + a short
Markdown) so the finished state is *demonstrated, not asserted*.

Public surface:

- [`count_registry()`](../finn/finn_report.py:74) — unique discovered FINN-koder + seen window.
- [`count_runs()`](../finn/finn_report.py:96) — search runs, pages fetched, docs seen.
- [`count_matches()`](../finn/finn_report.py:122) — listing overlays + how many resolved to a card.
- [`count_pricing()`](../finn/finn_report.py:131) — priced ads, `with_value`/`with_ratio`, basis tally, card sums.
- [`count_archive()`](../finn/finn_report.py:169) — fully archived ads.
- [`intent_distribution()`](../finn/finn_report.py:190) — ads per `finn_identify` label, deduped by kode.
- [`coverage()`](../finn/finn_report.py:222) / [`render_markdown()`](../finn/finn_report.py:261) /
  [`build()`](../finn/finn_report.py:305) — compose, render, and write `coverage_<ts>.json|md`.
- CLI: `--registry`, `--searches-dir`, `--matches`, `--pricing`, `--annonser`, `--outdir`
  (default `data/finn/reports`), `--ts`, `--json`.

## Success criteria — met

- [x] Counts come from real files, never hard-coded; a missing artifact yields **zeros + a note**, no crash
      (`test_missing_artifact_is_zero`, `test_archive_missing_is_zero`).
- [x] `intent_distribution` **dedupes by `finn_kode`** and its `total` equals the unique-kode count
      (`test_intent_distribution_dedupes`).
- [x] `with_value`/`with_ratio` count only non-null `deal` fields (`test_count_pricing`).
- [x] Markdown has a section per stage (Discovery / Archive / Identify / Match / Pricing)
      (`test_coverage_and_render_markdown`).
- [x] Output JSON + Markdown are timestamped and uniquely named (`test_cli_writes_files`).
- [x] Gaps surface loudly (`57 card(s) enumerated but none priced`, `only 1 of 106 discovered ads are
      archived`) — emitted, not hidden.

## Evidence

`uv run tests/test_finn_report.py` → **10 tests, OK**.

Full suite: `test_finn_ad_parse` 14 · `test_finn_search_catalog` 10 · `test_finn_identify` 10 ·
`test_finn_cards` 12 · `test_finn_price` 11 · `test_finn_tables` 11 · `test_finn_report` 10
→ **78 tests OK**.

Real run (`uv run finn/finn_report.py`) → `data/finn/reports/coverage_2026-10-08-031446.md`:

```
## Discovery
- unique ads in registry: **106**
- search runs: 3  ·  pages fetched: 4  ·  docs seen: 212
- seen window: 2026-10-02T16:25:30Z → 2026-10-08T02:57:43Z

## Archive
- ads fully archived: **1** of 106 discovered

## Identify
- ads ranked (latest discovery set): **53**
  - named-card: 17
  - none: 26
  - tier1-set: 7
  - tier2-set: 3

## Match
- listing overlays: 11  ·  resolved to a card: **3**

## Pricing
- priced ads: 4  ·  with a market value: **1**  ·  with a deal ratio: **1**
- basis: {'none': 3, 'listing_best': 1}
- enumerated cards: 57  ·  priced: **0**

## Notes / gaps
- 57 card(s) enumerated but none priced (cache cold / budget)
- only 1 of 106 discovered ads are archived
```

---

## Program report (0001 → 0007)

**What runs today** (all `uv run`, all offline-capable, all append-only):

| Stage | Module | Output | Tests |
|---|---|---|---|
| Parse an ad | `finn/finn_ad.py` | `data/finn/annonser/<kode>/…json` | 14 |
| Discover / delta | `finn/finn_search.py` | `searches/<ts>/`, `registry/pokemon-kort.json` | 10 |
| Rank intent | `finn/finn_identify.py` | `identify` blocks | 10 |
| Structure card lists | `finn/finn_cards.py` | per-card rows + provenance | 12 |
| Price ad + cards | `finn/finn_price.py` | `matches/pricing.jsonl` | 11 |
| Build tables | `finn/finn_tables.py` | `tables/listings_*.csv\|html`, `cards_*.csv` | 11 |
| Coverage report | `finn/finn_report.py` | `reports/coverage_*.json\|md` | 10 |

**Finished state vs. `SCRAPING_PROMPT.md`.** The headline deliverable exists and is proven: a sortable
listings table with the deal ratio (`market_value_nok / asking_price_nok`) next to the asking price, plus a
per-card table — built deterministically from priced records. The **machinery** for the full pipeline is
complete and tested end-to-end.

**Honest coverage gap (the program is *built*, not yet *filled*).** Only **1** of **106** discovered ads has
been fully crawled, and only **1** priced record carries a real deal ratio. Nothing is faked to close the
gap — the report prints it. To reach the brief's "every interesting ad" finished state, the remaining work
is mechanical, not new code:

1. **Crawl** the 106 registry koder through `finn_ad.py` (politely: delays + jitter, low frequency).
2. **Price** them with `finn_price.py` (live, within the 100/h · 1000/day budget; the cache makes re-runs
   cheap). Per-card prices need the description card lists plus live PokeWallet search calls.
3. **Re-run** `finn_tables.py` + `finn_report.py` — both are idempotent re-projections of what is on disk.

**Known limitations carried forward (see 0005/0006 findings):** the committed cache key drifts from the
current planner (0005 #1); the default 24 h cache window marks the old snapshot stale (0005 #2); price
sub-type (`holo` vs `reverse holo`) is captured but unused (0005 #5); the cards table has no HTML twin by
design (0006 #4).

## Findings (honest, not suppressed)

1. **Intent proxy is visible, not hidden.** "Interesting ad" is proxied by `finn_identify` rank > 0; the
   report prints the *full* distribution (26 of 53 ranked ads are `none`) so the proxy's cost is auditable.
2. **`docs=212` > `koder=106`.** Docs are counted per page (the same ad recurs across runs), while the
   registry dedups by kode — a deliberate difference, and the report shows both so it cannot be misread.
3. **`matched=3/11` overlays** — the 11 overlays are hand-run samples, not the full crawl; the number is a
   smoke signal, not a coverage claim.
4. **No artifacts were mutated.** This stage only reads; all outputs are new timestamped files
   (`unique_path`), and re-running is safe.
