# HANDOFF — scrape every Pokémon card listing on finn.no, price them, build the table

> **This whole file is the starting prompt for the next agent.** It is written so the agent does **not**
> need to ask the user anything. Every decision is either specified below or given a default in §7. If
> something is still ambiguous: pick the most reasonable option, record it as an assumption in the work
> item's `RESULT.md`, and **keep going**. Do not stop to ask.

---

## 1. Mission — the single outcome

Autonomously, end to end:

1. **Discover** every Pokémon-card listing on finn.no across a broad query set (all pages, multiple sorts).
2. **Scrape** each listing into structured JSON (machine-read fields + max-size images) — one folder per
   **FINN-kode** (the primary key everywhere).
3. **Price** each listing: match it to PokeWallet cards and record an estimated market value in NOK next to
   the seller's asking price, so a deal ratio is computable.
4. **Build the table** that brings it all together (listings + parsed cards + prices), sortable/filterable,
   with honest coverage and freshness columns.
5. **Prove it**: committed tests, printed coverage counts, and a program report.

"Thousands of cards" is the expectation: the search space yields thousands of ads, and many ads enumerate
many cards. Always work at the **listing** level; work at the **card** level wherever a description
enumerates cards.

## 2. Start here — context discipline (mandatory)

- Read `AGENTS.md` (always-on bootstrap) and `WORKFLOW.md` **once**. That is your working protocol: small
  self-contained `work/NNNN-*/` items, **success criteria + tests written first**, implement end to end,
  verify against real output, record evidence, then the next item.
- **Do not read `PROJECT-PLAN.md` or `scraper-parser-spec.md` end-to-end.** Open only the sections a task
  needs; the repo map in `AGENTS.md` §3 tells you where things live.
- You are an **orchestrator of small items**, not one giant script. A single item must be verifiable on its
  own and finishable in one context window. This program spans **many sessions** — everything must be
  resumable, and each item must leave the repo in a working, documented state.
- **Never use `ask_followup_question`.** If you are blocked (e.g. the API key is missing), do every
  non-blocked part, mark the blocked part clearly, and report at the end — do not halt the whole program.

## 3. What already exists (reuse it, don't reinvent)

- `finn/finn_search.py` — search discovery; decodes the server-rendered JSON (docs / metadata / filters);
  supports `--all-pages`, multiple `--sort`, `--param key=value`, and a per-query seen-kode **registry +
  delta report**. Output under `data/finn/searches/`.
- `finn/finn_ad.py` — one folder per ad under `data/finn/annonser/{kode}_{slug}/`: immutable raw HTML,
  parsed `{kode}.json`, max-resolution `photos/`, append-only `manifest.json`; global log
  `data/finn/_log/ad_scrapes.jsonl`.
- `finn/finn_matcher.py` — heading/ad → **ranked PokeWallet candidates + price**; append-only query cache
  `data/finn/_cache/query_cache.jsonl`; overlay payload; output `data/finn/matches/matches.jsonl`.
- `finn/finn_searches.py` — the built-in query set (extend it; it is the source of the search space).
- `pokewallet/pwlib/` — API client, budget handling, price extraction, set index, config, utils.
- `sheet/build_sheet.py` — turns local data into table payloads. **There may be no Google Sheets MCP server
  available**; if it is not, the local CSV/HTML in §8 *is* the deliverable — do not block on Sheets.

Run everything with `uv run <script>.py`. Add dependencies only via the `uv-dependency-injector` skill.
If a module's current behaviour is unclear, read its `--help` (it is detailed) or grep (`search_files`) —
do not read whole large files.

## 4. Program decomposition (a guide — adjust as you learn; keep every item small)

Create one `work/NNNN-*/` folder per item, in this order. Each item: `TASK.md` (define success + tests
yourself) → failing tests → implementation → real evidence → `RESULT.md`.

1. **Test + fixture harness.** Commit a real saved ad HTML (and a search HTML) under `tests/fixtures/` and
   assert the machine-read fields. This is the regression net everything else depends on.
2. **Machine-read field gaps.** From a real parse, `condition` came back empty, `favorite_count` was null,
   `card_list_raw` is not separated from `description_raw`, and spec §2.1 lists `shipping_nok`,
   `trygg_betaling_nok`, `fiks_ferdig`, `item_ref` — verify/fill these, one small group per item, each with
   a fixture + test.
3. **Search discovery at scale.** Run the broad query set (extend `finn_searches.py`: set names, misspellings,
   Norwegian/English variants, `sub_category`/`product_category` filters) × several sorts × all pages. Build
   and update the **registry**; report `new` / `still-active` / `gone`. Re-runs must be safe and cheap.
4. **Ad scraping at scale (resumable).** Scrape every **new** kode (`--from-jsonl`), with polite delay +
   jitter, images at max resolution. Skip work already done; log every failure loudly. This is the step that
   produces "thousands of ads" — it must be safe to stop and resume at any time.
5. **Card-list structuring (LLM-derived).** Where a description enumerates cards (`Liste over kort:` …),
   extract per-card records (name, set/variant hints, count) with **provenance** (`input_excerpt`, `method`,
   `confidence`, `produced_at`), reproducible, never hand-edited. Reconcile title-vs-description counts and
   **flag** mismatches (do not silently pick one).
6. **Pricing at scale (budget-aware).** Reuse `finn_matcher.py` + the query cache to price listings; price
   distinct **cards** where parsed. Cache-first (a repeat card costs zero calls). Record estimated market
   value, source (TCGPlayer/CardMarket), FX rate used, timestamp. Respect the budget and resume.
7. **Build the table** (§8).
8. **Coverage + program report** (§9).

## 5. Guardrails (non-negotiable — from `AGENTS.md` §4)

- **`uv run` only.** Never `python` / `pip install` / `uv pip install` / `uv run --with` / `uv run python`.
- **Never delete a file** — move to a `.trash/` folder in the same directory. Append-only: raw pages, images,
  registries, matches, caches, and logs are never mutated in place.
- **Never suppress errors.** Print counts and compare to expectations; a mismatch is loud. No "success"
  printed without a check behind it.
- **Writes must fail rather than overwrite.** Idempotent and resumable by default.
- **Timestamps:** `%Y-%m-%d-%H%M%S`.
- **Git is read-only** unless the user asks.
- **Never edit a test to make it pass.** A red test is a finding — report it (`WORKFLOW.md` §4).
- **API budget is shared:** **100 requests/hour, 1000/day**; cached responses still count. Never spend the
  last ~10/hour; reserve them. On exhaustion, stop cleanly, record state, and resume next window.
- **Never commit the API key.** Read it from the `API_KEY_POKEWALLET` env var.
- Be **polite to finn.no**: delays + jitter between requests, low volume, personal use.

## 6. Budget reality (read this or you will fail)

You cannot price thousands of cards in one hour. Design for **breadth first, depth over time**:
discovery + scraping cost **no API calls** and should complete first; pricing then proceeds across hourly
windows, prioritising (a) listings that look underpriced, (b) distinct cards not yet in the cache. Because
`matches` and the query cache are append-only and cache-first, **every session makes durable progress** and
re-running is cheap. Ship a working, resumable pipeline that keeps improving — do not fake completeness.

## 7. Decisions already made (defaults — do NOT ask)

- **Search space:** start from `finn/finn_searches.py`; add Pokémon set names, common seller misspellings/
  variants, and the `sub_category=1.86.285` (Samleobjekter) / `product_category=2.86.285.396` (Samlekort)
  filters. Sorts: at least `PUBLISHED_DESC` + `RELEVANCE`; union results.
- **Price source:** primary = TCGPlayer `market_price`; fall back to CardMarket (`trend`, then `avg`). Store
  **both sources when present** plus which one was chosen.
- **Currency:** market value converted to **NOK**; store the FX rate and its date. Asking price is NOK.
- **Deal ratio:** `market_value_nok / asking_price_nok` (and its inverse where useful). FINN asking price is
  never blended into the market-price column.
- **Snapshot cadence:** price as often as the budget allows (protect a ~10/hour floor); never re-price a
  fresh cached value.
- **Crawl politeness:** base delay ~1.0 s + random jitter; modest volume; stop-and-resume rather than burst.
- **Card list:** extract only when the text enumerates cards; otherwise mark `card_list_present = false`.
- **Google Sheet:** publish only if an MCP server is available; otherwise the local CSV/HTML table is final.
- **Ambiguity:** choose the most reasonable option, write it as an assumption in `RESULT.md`, proceed.

## 8. The table (the deliverable)

Local, append-only source of truth **plus** a generated, human-usable table:

- Source of truth (append-only): the per-ad archives under `data/finn/annonser/`, the registries/logs under
  `data/finn/`, and `data/finn/matches/matches.jsonl`.
- Generated table(s) under `data/finn/tables/` with a timestamp and a `latest` copy:
  - **Listings table** — one row per FINN-kode: identity, url, title, asking price, status
    (Aktiv/Inaktiv/Solgt), location, images, parsed-card count, matched PokeWallet card(s), market value
    (NOK) + source, FX rate, **deal ratio**, price/status timestamps, coverage/freshness flags.
  - **Cards table** — one row per parsed card: parent FINN-kode, card name, set/variant hints, count,
    matched PokeWallet id/name, market value, provenance.
- Emit as CSV (and a self-contained HTML table if cheap). Exact schema is yours to define — make it
  sortable and self-explanatory, and keep machine-read vs derived vs human columns clearly separated.

## 9. Definition of Done (program)

- [ ] Committed tests pass; the harness covers parsing + matcher + table build with real fixtures.
- [ ] Discovery ran the full query set; the registry reports `new`/`still-active`/`gone` totals.
- [ ] Every discovered ad has been scraped (or is on a visible, resumable "todo" list with reasons).
- [ ] Pricing is cache-first and resumable; coverage is reported (ads priced / total, cards priced / parsed).
- [ ] The table(s) build from local data and open cleanly; columns show asking price vs market value.
- [ ] A program report (`work/<id>/RESULT.md` and a short `work/` summary) states: counts, commands, the exact
      point to resume from, and any assumptions you made.
- [ ] Nothing was deleted; all failures are visible; no unverified "success".
