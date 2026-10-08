# TASK 0002 — Wire the search catalog into discovery + fix the registry delta

- **Status:** in-progress
- **Owner:** Zoo (code mode)
- **Output artifact(s):** `finn/finn_search.py` (new helpers + `--search-set`/`--kind`/`--tier`/`--id`),
  `tests/test_finn_search_catalog.py`
- **Depends on:** none (001 recommended)

## Goal (one sentence)

Make `finn/finn_search.py` run the **canonical catalog** (`finn/finn_searches.py`) — not a hard-coded
query list — and report a correct `new` / `still-active` / `gone` registry delta per query.

## Why / context

`SCRAPING_PROMPT.md` §3: `finn_searches.py` is the single source of truth for what Marius wants; §4 says
to verify `finn_search.py` consumes it via `--search-set` and to wire it if missing. It **is missing** —
`finn_search.py` only has `-q` and a small built-in `DEFAULT_QUERIES` list, and never imports the catalog,
so none of the Tier-1/Tier-2 sets, named cards, aliases, per-def params, sorts or page budgets are used.

The registry delta is also wrong today: `new_here` is computed *after* the registry is mutated (so it is
always empty), and the `gone`/`still-active` totals are never reported — only logged as a list.

## In scope

- `finn_search.jobs_from_defs()` — expand catalog search-defs into concrete (query, sort, params, max_pages) jobs.
- `finn_search.load_search_set()` — load defs from `finn_searches.search_defs(kind, tier, ids)`.
- `finn_search.compute_delta()` — pure `new` / `still_active` / `gone` from (known_before, seen_now).
- CLI: `--search-set`, `--kind`, `--tier` (repeatable `--id`); per-def params/sorts/max_pages drive the run.
- A **side-effect-free** `--dry-run` (plan + print only, writes nothing).
- Correct delta reporting + a `delta.jsonl` row carrying the three groups.

## Out of scope (do NOT touch)

- The fetch/parse internals (`http_get`, `parse_search_state`, `doc_record`) — unchanged.
- `finn_searches.py` catalog content (this item consumes it; extending the catalog is a later item).
- Scraping ads (`finn_ad.py`), matching, pricing, tables.

## Success criteria (DEFINE THESE YOURSELF, before coding)

- [ ] `--search-set` runs the full catalog: jobs carry each def's params (`sub_category=1.86.285`,
      `product_category=2.86.285.396`), sorts and `max_pages`.
- [ ] Ad-hoc `-q` still works and uses the CLI sort/max-pages (backwards compatible).
- [ ] Catalog defs keep their **own** sorts/max_pages (CLI `--sort`/`--max-pages` do not override them).
- [ ] `--kind`/`--tier`/`--id` narrow the job set exactly as `finn_searches.search_defs` does.
- [ ] `--dry-run` prints every planned URL, reports `planned_pages` == Σ(max_pages × len(sorts)),
      and writes **zero** files.
- [ ] `compute_delta` returns disjoint `new` / `still_active` / `gone` sets that partition the union.
- [ ] The per-query delta line prints all three counts.

## Test plan (write these tests FIRST — under `tests/`)

| Test | Input | Expected |
|---|---|---|
| `test_catalog_jobs_have_params_and_sorts` | `search_defs("all")` | one job/def; card params present; sorts≥1; pages≥1 |
| `test_adhoc_falls_back_to_cli` | ad-hoc def (no sorts/pages) | cli sorts/pages used; cli `--param` appended |
| `test_catalog_defs_keep_their_own_sorts` | set def with its own sorts/pages | cli values ignored |
| `test_params_and_paging` | `build_url(...)` | def params + `page=2` present; no `page=1` |
| `test_new_still_active_gone` | known={a,b}, seen={b,c} | new=[c], still_active=[b], gone=[a] |
| `test_no_change` | known=seen={a} | new=[], gone=[], still_active=[a] |
| `test_search_set_dry_run_expands_catalog` | `--search-set --dry-run` | rc 0; `planned_pages==Σ`; params in URLs |
| `test_kind_filter_limits_jobs` | `--search-set --kind card --dry-run` | jobs==#cards; planned_pages==Σ |
| `test_dry_run_writes_nothing` | snapshot registry/_log/searches/filters before/after | identical |

## Evidence to capture

- `uv run tests/test_finn_search_catalog.py` output (count + OK).
- `uv run finn/finn_search.py --search-set --dry-run | findstr /C:"DRY RUN"` → jobs + planned_pages.

## Open questions / assumptions

- Catalog defs are authoritative for sorts/max_pages; CLI `--sort`/`--max-pages` only apply to ad-hoc `-q`
  queries. Documented in `--help`; recorded here as the design decision.
- Registry stays keyed by query slug. Multiple defs that share a query (e.g. "Base Set") share one registry,
  so cross-def duplicates count as `still_active`, never double-`new` — the intended FINN-kode dedupe.
- `--dry-run` previously still created run/registry/log directories; it now returns before any write.
