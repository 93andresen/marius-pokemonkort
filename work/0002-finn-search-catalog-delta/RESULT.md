# RESULT 0002 — Wire the search catalog into discovery + fix the registry delta

- **Status:** done
- **Date:** 2026-10-08
- **Artifacts:** `finn/finn_search.py` (helpers `load_search_set`, `jobs_from_defs`, `compute_delta`;
  CLI `--search-set`/`--kind`/`--tier`/`--id`; side-effect-free `--dry-run`; corrected delta),
  `tests/test_finn_search_catalog.py`, live run `data/finn/searches/2026-10-08-025742/`.

## What ran

### 1. Tests (offline)

```
uv run tests/test_finn_search_catalog.py
→ Ran 10 tests ... OK
  [catalog] 40 jobs from 40 defs
  [dry-run] planned_pages=78 (from 40 defs)
```

### 2. Catalog planning (offline CLI, real catalog)

```
uv run finn/finn_search.py --search-set --dry-run
→ FINN search DRY RUN  jobs=40  (no network, no files written)
  [broad-pokemon-kort | pokemon kort | PUBLISHED_DESC | page 1] ...&category=0.86&sub_category=1.86.285&product_category=2.86.285.396
  [set-jungle | Jungle | PUBLISHED_DESC | page 2] ...&product_category=2.86.285.396&page=2
  [card-umbreon | umbreon | PUBLISHED_DESC | page 1] ...&product_category=2.86.285.396
  DRY RUN: jobs=40  planned_pages=78  files_written=0
```

40 search definitions = 6 broad (×2 sorts ×2 pages) + 20 sets (×1 sort ×2 pages) + 14 cards (×1 page).

### 3. Live discovery (1 courteous page) — proves fetch→parse→registry→delta

```
uv run finn/finn_search.py -q "pokemon kort" --max-pages 1
→ GET ... -> 200 (958886 bytes, 1.15s)
  docs=53  num_results=53  match_count=34509  paging={'current': 1, 'last': 50}
  [pokemon kort] delta: new=53  still_active=0  gone=53  seen=53  known_before=53
  DONE  run=2026-10-08-025742  pages=1  docs=53  new_koder=53
```

The delta partition is internally consistent: 53 seen, 53 previously-known, 0 overlap ⇒ 53 new / 0
still-active / 53 gone. `match_count=34509` confirms the brief's "thousands of ads".

## Evidence vs success criteria

| Criterion | Result |
|---|---|
| `--search-set` runs full catalog with per-def params/sorts/pages | ✅ 40 jobs, params in every URL |
| ad-hoc `-q` still works with CLI sort/max-pages | ✅ live run above |
| catalog defs keep their own sorts/max_pages | ✅ `test_catalog_defs_keep_their_own_sorts` |
| `--kind`/`--tier`/`--id` narrow the set | ✅ `test_kind_filter_limits_jobs` (card=14) |
| `--dry-run` plans only, writes zero files | ✅ `test_dry_run_writes_nothing`; `files_written=0` |
| `compute_delta` disjoint, partitions union | ✅ 3 tests incl. `test_partition` |
| per-query delta prints new/still_active/gone | ✅ live output above |

## Design decisions / assumptions

- Catalog defs are authoritative for sorts/max_pages; CLI `--sort`/`--max-pages` apply only to ad-hoc `-q`
  defs (which carry `None` and fall back to the CLI values). Stated in `--help`.
- Registry stays keyed by query slug; defs sharing a query share one registry, so cross-def duplicates are
  `still_active`, never double-`new` (the FINN-kode dedupe the brief asks for).
- `--dry-run` now returns **before** creating any run/registry/log directory (previously it created empty
  dirs and wrote an empty delta). This is a deliberate behaviour change; it makes planning truly read-only.
- `run.json` now records `search_set`, the full `searches[]` job list and `extra_params` (replacing the old
  `queries`/`sorts`/`max_pages` scalars) — additive, keeps `queries` as a string list for compatibility.

## Residual / follow-ups (not blockers)

- A **full catalog live discovery** (78 pages, all tiers/kinds) has not been run end-to-end yet; it is a
  ~4-minute courteous sweep and belongs to its own item ("run discovery across the catalog").
- The single live run used `-q`, not `--search-set` with multiple defs, so the shared-query registry path is
  covered by unit tests + dry-run rather than a multi-def live run. Safe, but noted.

## Resume point

Item complete. Next: **0003** — build the missing `finn/finn_identify.py` (rank ads by Marius' interesting
sets/cards using `finn_searches.SETS`/`CARDS`), then 0004 (card-list structuring).
