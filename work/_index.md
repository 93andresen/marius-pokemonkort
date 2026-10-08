# work index

One row per work item. Append only; **never renumber**. Status: `todo` / `in-progress` / `done` / `blocked`.

| ID | Title | Status | Notes |
|---|---|---|---|
| 0001 | Offline parse regression net for `finn/finn_ad.py` | done | 14 stdlib tests on a real capture; `tests/test_finn_ad_parse.py` |
| 0002 | Wire the search catalog into discovery + fix registry delta | done | `--search-set` runs catalog (40 defs/78 pages); live run delta new=53/seen=53; `tests/test_finn_search_catalog.py` |
| 0003 | Build `finn/finn_identify.py` (rank ad by intent) | done | reuses `SETS`/`CARDS`, word-boundary matching; real distribution tier1=7/card=17/tier2=3/none=26 of 53 |
| 0004 | Structure enumerated card lists (`finn/finn_cards.py`) | done | 57 cards from real capture w/ provenance; fixed U+2028 drift (canonical `logical_lines`); `tests/test_finn_cards.py` 12 OK |
| 0005 | Price an ad + each enumerated card (`finn/finn_price.py`) | done | cache-first, budget-aware; `confidence_of`/`deal_math`/`price_ad` + `deal.ratio`; real cached value 0 calls; `tests/test_finn_price.py` 11 OK; suite 57 OK |
| 0006 | Sortable listings + cards tables (`finn/finn_tables.py`) | done | pure formatting of `pricing.jsonl`; best-deal-first; CSV + self-contained sortable HTML under `data/finn/tables/`; `tests/test_finn_tables.py` 11 OK; suite 68 OK |
| 0007 | Program coverage report (`finn/finn_report.py`) | done | pure accounting of all artifacts; discovers 106 koder/1 archived/1 deal ratio & flags the gaps; `reports/coverage_*.json\|md`; `tests/test_finn_report.py` 10 OK; suite 78 OK |

---

## Starting point (read before scoping the first item)

> **The active program brief is [`../SCRAPING_PROMPT.md`](../SCRAPING_PROMPT.md)** — scrape all finn.no
> Pokémon listings, price them via the PokeWallet API, and build the table. Start there; it defines the work.

The pipeline already runs: `finn/finn_ad.py` and `finn/finn_search.py` parse pages both live and offline.
There is **no committed test suite yet** (`tests/` is empty; `data/finn/_probe/test_agent.py` is a
throwaway probe). So the highest-value first unit is usually a **regression net**, not a new feature.

**Evidence from a real parse** (`data/finn/annonser/475878513_.../475878513.json`, checked 2026-10-06):

- Extracted well: `finn_kode` (+ 4 cross-check candidates), `title`, `status`, `price_nok`,
  `lat`/`lon`/`postal_code`, `location_text`, `last_modified`, `gallery_count` + 25 `image_uuids`,
  `description_raw`, `breadcrumbs`, `similar_ads`.
- **Gaps to investigate** (leads, not conclusions): `condition` came back empty (`""`); `favorite_count`
  is `null`; `card_list_raw` is not separated from `description_raw` (this ad literally contains a
  `Liste over kort:` block); spec §2.1 also lists `shipping_nok`, `trygg_betaling_nok`, `fiks_ferdig`
  and `item_ref` — confirm whether these are captured.

## Suggested sequence (each item is still scoped + given tests by its owner)

1. **Offline test + fixture harness** for `finn_ad.py`: parse a committed saved HTML capture and assert the
   machine-read fields. This is the regression net every later change depends on.
2. **Fill / verify the machine-read field gaps** above — one field (or small group) per item, each backed by
   a fixture + test.
3. FINN **search → discovery + delta detection** (`new` / `still-active` / `gone`), with pagination verified.
4. **Card-list structuring** (LLM-derived) from `description_raw`, with provenance + count reconciliation.
5. End-to-end **golden path**: raw capture → parsed JSON → matched price → Sheet row.
6. **Sheet ingestion** of parsed ads (two-layer, append-only: raw + current).

> These are **areas, not tasks**. Split each along verification boundaries; if it can't be verified alone or
> can't fit one context window, split smaller. The item owner defines the success criteria and tests.
