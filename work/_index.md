# work index

One row per work item. Append only; **never renumber**. Status: `todo` / `in-progress` / `done` / `blocked`.

| ID | Title | Status | Notes |
|---|---|---|---|
| 0001 | Offline parse regression net for `finn/finn_ad.py` | done | 14 stdlib tests on a real capture; `tests/test_finn_ad_parse.py` |

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
