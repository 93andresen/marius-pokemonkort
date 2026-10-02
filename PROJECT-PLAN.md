# PROJECT-PLAN.md — Marius' Pokémon Card Portfolio + FINN.no Toolkit

> **This is the master plan.** It is the single document that lets any agent (or human) resume this
> project at any time by reading it top-to-bottom. If something here disagrees with a more specific
> document, the more specific document wins — but the *decisions* below are the source of truth for
> *why* things are built the way they are.
>
> **Last updated:** 2026-10-02 (initial write).
> **Status:** Active build.

---

## 0. How to resume (read this first, in this order)

1. [`AGENTS.md`](AGENTS.md) — workspace conventions, hard rules, and the canonical Google resource IDs.
2. **This file** — project map, architecture, decisions, roadmap.
3. [`scraper-parser-spec.md`](scraper-parser-spec.md) — the FINN scraping pipeline constitution.
   Note **§0.5 PIVOT**: we extract structured data (JSON), we do **not** convert pages to Markdown
   (`web_to_md.py --js` is retired).
4. [`docs/pokewallet_io_api-docs.md`](docs/pokewallet_io_api-docs.md) — the PokeWallet API reference.
5. [`docs/pokewallet_io_api-VERIFIED-NOTES.md`](docs/pokewallet_io_api-VERIFIED-NOTES.md) — **live**-verified
   facts that differ from or extend the API docs (created during this project; see §5.3).
6. `CHANGELOG.md` (runtime log) and the `logs/` + `state/` folders — running status and history.

**Golden rule:** if the build was interrupted, do not start over. Check the `state/` folder and the
"Resume checklist" in §13 to find the last completed step, then continue from there.

---

## 1. The two goals (one repo, two deliverables)

This repo has **two** intertwined products. Both must work, both are valuable, and the second is the
user's declared favourite.

### Goal A — Portfolio tracker / pricing engine
Turn Marius' Collectr export into a **living, price-tracked portfolio** inside a Google Sheet:

- Price every card in [`getcollectr/marius_pokemon_cards_collectr_export_2026-10-02-052742.csv`](getcollectr/marius_pokemon_cards_collectr_export_2026-10-02-052742.csv)
  against the PokeWallet API (TCGPlayer + CardMarket price sources).
- Capture **price history over time** (snapshots), because history is the one asset we cannot
  retroactively create — so we start capturing **immediately** and keep capturing.
- Deliver **overviews, dashboards and sorting** the user can actually use (totals, allocation,
  movers, source coverage, missing data, etc.).
- Save **everything** the API returns to disk (append-only, never deleted).

### Goal B — The FINN.no "goldmine" toolkit *(the real prize)*
Augment [finn.no](https://www.finn.no) Pokémon-card listings with instant, trustworthy price data,
live, while browsing:

- Hover overlays on listings showing card identity + market price.
- Hotkey → enrich the current ad or a clipboard link.
- Trigger on URL change (SPA navigation) so deep-linking into an ad auto-enriches it.
- **Autocomplete / fuzzy matching** of cards, because sellers type garbage.
- Respect the **100 calls/hour** API budget — rank candidates, cap lookups, cache aggressively.
- Archive the **entire browsing history** so we can answer questions like
  *"Find all the Pichu's I have looked at in the last 4 weeks."*
- Store PriceCharting links as **unconfirmed** references; only treat them as confirmed when the user
  explicitly confirms them.

The user's words: *"The tool that actually fetches the prices from the finn.no searches is the real
goldmine."* and this is what will *"blow his mind."*

---

## 2. Hard constraints & conventions (summary; full rules in `AGENTS.md`)

| Area | Rule |
|---|---|
| **Never delete** | No file is ever deleted anywhere. To remove from the working tree, move it to a `.trash/` folder **in the same directory**. |
| **Never suppress errors** | All output is always visible in the terminal and in logs. No "completed successfully" unless actually verified. |
| **No silent partial success** | A failed step must produce a visible "failed" record (count of images downloaded vs. expected, failed-scrape list, etc.). |
| **Python** | Always run with `uv run <script>.py`. Never `python`, `pip install`, `uv pip install`, `uv run --with`, or `uv run python`. |
| **Dependencies** | Add via the `uv-dependency-injector` skill (`uv add --script`). **Never hand-edit PEP 723 `# /// script` blocks.** |
| **Idempotent & resumable** | Everything must be safe to re-run. Prefer checking-before-doing over overwriting. |
| **Overwrite safety** | Any move/rename must fail rather than overwrite an existing file. |
| **Git** | The user wants to *see the process*: commit **often**, including on failures and at milestones. Clear, scoped commit messages. |
| **Timestamps** | `%Y-%m-%d-%H%M%S` (24h, leading zeros, filename-safe, lexically sortable). |
| **Machine vs. human data** | Two kinds of data, separate columns, distinct owners (see `scraper-parser-spec.md` §2.0). Automation never writes human-owned columns. |
| **Immutable sources** | Raw API responses and raw scrapes are append-only archives. Parsing happens downstream and can always be re-run. |
| **Do not read** | `prompts-notes/prompts.md` is off-limits. |
| **Config** | Prefer storing settings in the user's configs folder (`c:\data\configs`, mirrored to Google Drive). |

---

## 3. Canonical IDs & secrets

```
Google Sheet ID      : 13TfMos8hP4zT3-Tf92F7ZE0hJ2r7cKJdEqvdj0gvtpM
Google Apps Script ID: 1zuV63oR_FZN1NRxlpgsrx5cFUuPc3p4ZgR2_pEZ8GZvJwvZEj6y2yUtr
PokeWallet base URL  : https://api.pokewallet.io
PokeWallet auth      : header  X-API-Key: <key>   (env var API_KEY_POKEWALLET is already SET)
```

- The **Sheet ID** canonical home is the **top of [`AGENTS.md`](AGENTS.md)** (moved there from
  `prompts-notes/notes.md`; see the spec update). Do not hard-code it in scripts — read it from a
  config/env with this as the documented default.
- **Never commit the API key.** It is read from the environment (`API_KEY_POKEWALLET`). A test key
  exists in `prompts-notes/notes.md` for reference, but scripts must always prefer the env var.
- **Note:** `notes.md` was observed to be modified externally during this session; treat it as
  user-owned. Never write to it.

---

## 4. Repository map

### 4.1 Current layout (verified 2026-10-02)

```
marius-pokemonkort/
├─ AGENTS.md                      # workspace rules + canonical IDs (top of file)
├─ AGENTS-suggestions.md          # advisory only ("do not assume everything is correct")
├─ PROJECT-PLAN.md                # ← THIS FILE
├─ scraper-parser-spec.md         # FINN pipeline constitution (§0.5 pivot)
├─ marius-pokemon-naming-findings.md
├─ .gitignore
├─ docs/
│   └─ pokewallet_io_api-docs.md  # API reference
├─ getcollectr/
│   └─ marius_pokemon_cards_collectr_export_2026-10-02-052742.csv   # 192 rows, NOK
├─ pokewallet-api-ideas/
│   ├─ pokemon-card-collection-tracker-plan.md      # 10-tab design (reference)
│   └─ pokewallet-free-api-ideas.md                 # free-plan capabilities
├─ pokewallet-api-ideas-prompts/
├─ prompts-notes/
│   ├─ notes.md                   # author-owned scratch (contains a test API key)
│   └─ scraper-parser-spec-prompt.md
├─ llm-history/
├─ s21-silver-downloads/
├─ data/
│   └─ pokewallet/_smoke/         # smoke captures: health/root/search + headers
└─ .trash/                        # archived older captures (e.g. .trash/finn/...)
```

### 4.2 Planned layout (we create these)

```
marius-pokemonkort/
├─ pokewallet/                    # API client + portfolio tools (Python, uv)
│   ├─ pokewallet_client.py       # generic CLI for EVERY endpoint (raw-saving, rate-aware)
│   ├─ resolve_portfolio.py       # CSV → canonical set_id/card_number matches
│   ├─ fetch_prices.py            # resumable snapshot capture for the whole portfolio
│   ├─ sync_sets.py               # pull + cache the full set index
│   └─ lib/                       # shared helpers (http, rate budget, paths, logging)
├─ finn/                          # structured finn.no scrapers (NO markdown)
│   ├─ finn_search.py             # search discovery + delta detection
│   ├─ finn_ad.py                 # one folder per ad: raw JSON + images + manifest
│   └─ finn_matcher.py            # search/ad → PokeWallet candidates → price overlay data
├─ tools/                         # browser augmentation
│   ├─ finn-enhance.user.js       # Tampermonkey/Violentmonkey userscript (overlays/hotkeys)
│   ├─ local_agent.py             # local HTTP helper the userscript calls (API + budget)
│   └─ history_logger.py          # append-only browsing-history store (JSONL)
├─ sheet/                         # Google Sheet build/publish
│   └─ build_sheet.py             # tabs, headers, formulas, dashboards, sorting
├─ data/                          # ALL local data (append-only)
│   ├─ pokewallet/
│   │   ├─ _smoke/                # (exists)
│   │   ├─ raw/                   # raw API responses, one JSON file per request
│   │   ├─ sets/                  # cached set index
│   │   └─ snapshots/             # portfolio price snapshots (JSONL / CSV)
│   └─ finn/
│       ├─ searches/              # raw search-page JSON captures
│       ├─ ads/                   # one folder per ad (raw JSON + images + manifest)
│       └─ history/               # browsing-history JSONL
├─ logs/                          # append-only run logs
└─ state/                         # resume/checkpoint state (what's done; see §4.4)
```

**`.gitignore` policy:** binary downloads (`photos/`, large image archives) are ignored — sources
and code are versioned, big binaries are not. Add specific ignore lines for `data/finn/ads/*/photos/`.

---

## 5. The PokeWallet API — verified facts

Base: `https://api.pokewallet.io`. Auth: `X-API-Key`. All facts below were verified live on
2026-10-02 (§5.3 lists doc discrepancies to be recorded in `docs/pokewallet_io_api-VERIFIED-NOTES.md`).

### 5.1 Endpoints

**Free / accessible:**

| Endpoint | Purpose | Cache TTL |
|---|---|---|
| `GET /` | API root / status | — |
| `GET /health` | Health check | — |
| `GET /search` | Find cards (`q`, `page`, `limit`, filters) | 15 min |
| `GET /cards/:id` | Full card by id | 60 min |
| `GET /sets` | All sets | 120 min |
| `GET /sets/:setCode` | One set + its cards | 120 min |
| `GET /images/:id` | Card images | — |

**PRO-blocked on the free plan** (verified: returns `{"error":"Trial not activated", ...}`):

```
/prices/:setCode
/cards/:id/price-history
/sets/:setCode/statistics
/sets/trending
/sets/:setCode/completion-value
/analytics/top-cards
```

→ **Consequence:** we cannot bulk-pull prices. We must price **per card** via `/search` or
`/cards/:id`, and we cannot get server-side price history — so **we create our own history** by
snapshotting on a schedule. This is why the user insists we start **immediately**.

### 5.2 Rate limits (verified)

```
X-RateLimit-Limit-Hour: 100        X-RateLimit-Remaining-Hour: ...
X-RateLimit-Limit-Day: 1000        X-RateLimit-Remaining-Day: ...
```

- **100 requests/hour, 1000/day.**
- Cached responses (`X-Cache: HIT`) **still count** against the quota.
- Track remaining budget; stop cleanly before exhaustion and record state so we resume later.

### 5.3 Raw response shape (verified via `/search?q=pikachu&limit=1`)

```jsonc
{
  "query": "pikachu",
  "results": [
    {
      "id": "pk_4c87dcac6b799948e67647780ac444d88e323e31e0b4fefa55dce4be7a587ca712c9310e891e1ce44827",
      "card_info": {
        "name": "Basic Lightning Energy - Pikachu 4",
        "clean_name": "Basic Lightning Energy Pikachu 4",
        "set_name": "Battle Academy 2024",
        "set_code": "BA24",            // docs example said "BA2024" — live value is "BA24"
        "set_id": "23520",
        "card_number": "004",
        "rarity": "Common",
        "card_type": "Basic Lightning Energy",
        "product_type": "card",        // NOT in docs — present live
        "hp": null, "stage": null, "card_text": null,
        "attacks": [], "weakness": null, "resistance": null, "retreat_cost": null
      },
      "images": { "languages": ["en"] },
      "tcgplayer": {
        "prices": [{
          "low_price": 0.1, "mid_price": 0.17, "high_price": 19.82,
          "updated_at": "2026-10-02T10:48:30.269288",
          "market_price": 0.14, "direct_low_price": null,
          "sub_type_name": "Normal"
        }],
        "url": "https://www.tcgplayer.com/product/556892"
      },
      "cardmarket": null
    }
  ],
  "pagination": { "page": 1, "limit": 1, "total": 821, "total_pages": 821 },
  "metadata": { "total_count": 821, "tcg": 489, "cardmarket": 482, "tcg_only": 339, "cardmarket_only": 332, "both_sources": 150 }
}
```

**Card id formats:** `pk_<hex>` = TCGPlayer-backed card; bare `<hex>` = CardMarket-only card.

**Price field reference**

- TCGPlayer: `low_price, mid_price, high_price, market_price, direct_low_price, updated_at, sub_type_name`
- CardMarket: `avg, low, avg1, avg7, avg30, trend, updated_at, variant_type`

**Best lookup key (VERIFIED — see `docs/pokewallet_io_api-VERIFIED-NOTES.md` §6):** the reliable
key is the **canonical set NAME + card number** (e.g. `q="ancient roar 90"`). The docs' `set_id`
key is exact **only for positive** ids; several sets have **negative** ids (`LOT=-113`, `CS5.1C=-38`,
`CS6.1C=-42`, `CBB4C=-240`, `CBB5C=-242`) which return *unrelated* cards sharing the same number.
`set_code` also sometimes differs (docs `BA2024` vs live `BA24`) and Chinese/JP set ids in the index
do not match the API card's actual `set_id`. So the fetcher tries **`set_id` → `set_code` →
canonical set name**, then **validates** every candidate (`validate_match`) before accepting a price.
Never trust a `/search` hit without validation.

### 5.4 Discrepancies vs. `docs/pokewallet_io_api-docs.md`

1. Live API version is **1.7.1** (docs say 1.1.0).
2. `product_type` field present in `card_info` (undocumented).
3. `set_code` live value `BA24` vs. docs example `BA2024` — do not rely on `set_code`; prefer `set_id`.

→ Record these in `docs/pokewallet_io_api-VERIFIED-NOTES.md` and reference that file from the docs.

---

## 6. Data-ownership model (applies everywhere)

From `scraper-parser-spec.md` §2.0, generalised to the whole system:

- **Machine-read** data (read straight off the API/page): written **only** by automation, **append-only**.
  Re-runs append new snapshots; they never mutate prior rows.
- **Derived / human** data (estimates, LLM output, manual notes, confirmations): written **only** by
  its owner. Automation never touches human columns; LLM columns are clearly labelled and regenerated.

**Why:** manual edits can never be silently reverted, and machine values can never be silently
contradicted. This is the core protection for the user's work.

---

## 7. Component specifications

### 7.1 `pokewallet/pokewallet_client.py` — generic API CLI *(build first)*
One script that exposes **every** endpoint. Requirements:

- Sub-commands mirroring the API: `root`, `health`, `search`, `card`, `sets`, `set`, `images`,
  and the PRO ones (`prices`, `price-history`, `statistics`, `trending`, `completion-value`, `top-cards`)
  so we can detect the day PRO unlocks.
- **Always saves the raw response** to `data/pokewallet/raw/<endpoint>/<timestamp>__<args>.json`
  (+ a `.headers` sidecar), before any parsing. This satisfies "save everything".
- **Rate-limit aware:** print `X-RateLimit-Remaining-*`; refuse to run if below a safety floor;
  support `--dry-run`.
- **RateLog:** append every call to `logs/ratelog.csv` (timestamp, endpoint, args, status, remaining-hour, remaining-day).
- **Flexible I/O:** `--json` (raw to stdout), `--summary` (human table), `--out <file>`.
- Idempotent: re-running re-fetches (new snapshot) but never overwrites an existing raw file
  (timestamped filenames guarantee uniqueness).

### 7.2 `pokewallet/sync_sets.py`
- Pull `/sets`, cache to `data/pokewallet/sets/sets_<timestamp>.json`.
- Build a lookup: set name (and aliases/JP/CN suffix handling) → `set_id` + `set_code`.
- Handles the Collectr set-name → PokeWallet set-name mismatches (e.g. `"Base Set 2"`, `(JP)`/`(CN)`).

### 7.3 `pokewallet/resolve_portfolio.py`
- Parse the Collectr CSV (NOK; beware quoted thousands like `"1,018.31"` — strip commas before float).
- For each row, resolve to a PokeWallet card: try `set_id + card_number`, then name+number, then
  fuzzy name; record **match confidence** and the chosen `id`.
- Output `data/pokewallet/resolved_portfolio_<timestamp>.csv` (append-only) with: original row +
  `pk_id`, `matched_name`, `matched_set_id`, `match_method`, `match_confidence`.
- **Unmatched rows are a visible, listable output** — never silently dropped.

### 7.4 `pokewallet/fetch_prices.py` — resumable snapshot capture
- Input: resolved portfolio. Output: `data/pokewallet/snapshots/portfolio_<timestamp>.jsonl` (one
  record per card: id, set_id, number, name, prices{}, source, fetched_at, remaining budget).
- **Budget-aware:** stop at the safety floor, write `state/price_run_<timestamp>.json` with what's
  done and what remains → resumable in the next hour.
- Prefer fetching by `id` (`/cards/:id`, 60-min cache) but fall back to `/search` for lookups.
- Never lose a completed card: each record is flushed as it is written (append-only JSONL).

### 7.5 `sheet/build_sheet.py` — spreadsheet build & publish
- Uses the Google Sheets MCP (`list_sheets`, `create_sheet`, `update_cells`, `batch_update_cells`,
  `get_sheet_data`) and/or Apps Script for scheduled logic.
- Creates the tabs in §8, writes headers, seeds data, and installs formulas for dashboards/sorting.
- Idempotent: re-running updates data ranges, never clobbers human columns.

### 7.6 FINN tools (`finn/`)
- **`finn_search.py`** — discover listings across the full parameter map (sorts, category filters,
  pagination). Extracts **structured JSON** directly (search-result payloads / `data-*` attrs) — no
  Markdown. Keeps a registry of FINN-kodes per query; reports new / still-active / gone. Union of
  `PUBLISHED_DESC` + `RELEVANCE`.
- **`finn_ad.py`** — one folder per ad keyed by **FINN-kode**:
  `finn/ads/{kode}_{slug}/` → `{kode}.json` (raw structured capture), `photos/01.jpg…` (transformed
  to max size via the UUID pattern `images.finncdn.no/dynamic/{SIZE}/item/{itemRef}/{uuid}`),
  `manifest.json` (url, timestamps, image list + count, status). Visible image-count check.
- **`finn_matcher.py`** — takes a search result or ad, produces ranked PokeWallet candidates +
  prices (budget-capped), outputs the overlay payload JSON the browser tool consumes.

### 7.7 Browser augmentation (`tools/`)
- **`finn-enhance.user.js`** — userscript for finn.no: injects price overlays into listing cards,
  a hotkey to enrich the current ad / clipboard link, and a URL-change observer (SPA nav) that
  auto-triggers enrichment. Talks to the local agent.
- **`local_agent.py`** — small local HTTP server: receives ad URLs from the userscript, calls
  `finn_matcher` + PokeWallet (respecting budget), returns overlay data. Caches results.
- **`history_logger.py`** — append-only JSONL of every ad the user viewed (FINN-kode, title,
  matched card ids, timestamp). Enables queries like *"all Pichu's viewed in the last 4 weeks."*
- **PriceCharting links** are stored (a `pricecharting_url` field) but marked **unconfirmed**;
  a value is only treated as confirmed when the user explicitly confirms it.

---

## 8. Google Sheet design

Built for **useful functionality**, not just data dumping: overviews, dashboards, sorting by anything.

| Tab | Purpose |
|---|---|
| `Collection` | One row per owned card: Collectr fields + `pk_id` + current price(s) + value (qty × price). |
| `PriceSnapshots` | Append-only: one row per card per capture (`fetched_at`, prices, source). This is our history. |
| `Sets` | Set index from `/sets` (set_id, code, name, counts). |
| `CardCatalog` | Resolved card metadata (name, set, number, rarity, images link, tcgplayer url). |
| `Movers` | Derived: biggest gainers/losers between the two most recent snapshots. |
| `Coverage` | Derived: matched vs. unmatched cards, TCGPlayer vs. CardMarket availability, missing prices. |
| `Dashboard` | Totals, allocation, top holdings, source split, freshness, budget status. |
| `Config` | IDs, thresholds, budget floors, feature flags. |
| `RateLog` | Mirror of API call log for budgeting visibility. |
| `FINN` | Listings seen: FINN-kode, title, price, matched card, market price, delta, status. |

**Sorting:** every data tab is a plain range so Google Sheets native sort/filter works everywhere;
derived tabs use `QUERY`/`SORT`/`FILTER` formulas so they stay live.

*(Detailed tab/formula design was drafted in `pokewallet-api-ideas/pokemon-card-collection-tracker-plan.md`
during the earlier phase — reuse the good parts, but the pivot to per-card snapshots takes priority.)*

---

## 9. Rate-budget strategy (the 100/hr constraint shapes everything)

- **Reserve a floor** (e.g. never go below ~10 remaining/hour) for interactive/browser use.
- **Priority order** for spending budget: (1) browser interactions the user triggers; (2) scheduled
  portfolio snapshot; (3) background enrichment/search discovery.
- **Cache first, call second:** reuse `data/` captures; only call when a fresh value is actually needed.
- **Snapshot cadence:** as often as the budget allows early (history is precious), then settle to a
  sustainable schedule. Record every snapshot so density ramps up over time.
- **Fail visibly:** when budget is exhausted, stop and log — do not silently skip cards.

---

## 10. Decisions log

| # | Date | Decision | Rationale |
|---|---|---|---|
| D1 | 2026-10-02 | Sheet ID canonical home = top of `AGENTS.md` | User request; spec updated. |
| D2 | 2026-10-02 | Retire `web_to_md.py --js`; extract **structured JSON** from FINN | User: Markdown conversion throws away data and is brittle. See spec §0.5. |
| D3 | 2026-10-02 | Build **one generic API client** covering every endpoint | User: "could just make a script that can be used for any of the api's functionalities." |
| D4 | 2026-10-02 | Create **our own price history** via snapshots | `/prices` and price-history are PRO-blocked; history can't be back-filled → capture now. |
| D5 | 2026-10-02 | Prefer `set_id`+`card_number` lookups | Far better disambiguation than names. |
| D6 | 2026-10-02 | Commit continuously, including failures | User: "I JUST WANT TO SEE THE PROCESS!" |
| D7 | 2026-10-02 | Store PriceCharting links as unconfirmed | User: not confirmation unless user confirms. |

---

## 11. Roadmap / milestones

Status legend: `[x]` done · `[-]` in progress · `[ ]` todo.

- [x] **M0 — Recon & verify.** Read all docs/docs; verify API key, endpoints, rate limits, response shape.
- [x] **M1 — Spec pivot.** `scraper-parser-spec.md` updated (Sheet ID ref + structured-scraping pivot). Committed.
- [-] **M2 — Plan.** This document. + `docs/pokewallet_io_api-VERIFIED-NOTES.md`.
- [ ] **M3 — API client.** `pokewallet_client.py` (all endpoints, raw-saving, rate-aware, RateLog).
- [ ] **M4 — Sets + resolution.** `sync_sets.py`, `resolve_portfolio.py`; produce resolved portfolio + unmatched list.
- [ ] **M5 — Price run.** `fetch_prices.py`; start capturing snapshots for the whole portfolio **immediately**.
- [ ] **M6 — Spreadsheet.** Build tabs, seed data, dashboards, sorting.
- [ ] **M7 — FINN search + ad scrapers** (structured JSON, folder-per-ad, images).
- [ ] **M8 — FINN matcher** (search/ad → candidates → prices, budget-capped).
- [ ] **M9 — Browser augmentation** (userscript + local agent + history logger).
- [ ] **M10 — "Show the friend" demo.** A single, polished command/flow that demonstrates the price overlay on live finn.no + the populated sheet.

*(User wants something cool ready "today" → M5 + M6 are the fastest visible wins; M8/M9 are the mind-blower.)*

---

## 12. Testing & verification

- `pokewallet/_smoke/` holds the initial smoke captures (health, root, search) — extend, never delete.
- Every script supports `--dry-run` where a call would be made.
- Verification is explicit: counts (rows resolved, images downloaded, cards priced) are printed and
  compared to expectations; mismatches are surfaced, not hidden.

---

## 13. Resume checklist (the operational "where was I?")

When resuming, do this:

1. `git log --oneline -20` and `git status` — see the last committed step (the commit log *is* the process).
2. Read `state/` for any checkpoint (e.g. an unfinished `price_run_*.json`).
3. Read the last entries in `logs/` and `logs/ratelog.csv` for the last run's outcome.
4. Find the highest **completed** milestone in §11, then continue from the next `[ ]` item.
5. Commit before and after each meaningful step.

**Next actions right now (in order):**
1. Write `docs/pokewallet_io_api-VERIFIED-NOTES.md` and commit (M2).
2. Build `pokewallet/pokewallet_client.py` (M3) and smoke-test every free endpoint.
3. Build `sync_sets.py` + `resolve_portfolio.py` (M4), producing the resolved CSV + unmatched list.
4. Start `fetch_prices.py` and **begin the first portfolio snapshot run** (M5).
5. Build the sheet (M6).

---

## 14. Open questions / to-confirm with the user

- Confirm the current **price source preference** (TCGPlayer `market_price` vs. CardMarket `trend`/`avg`)
  as the primary "value" column, or show both.
- Confirm the desired **snapshot cadence** given the 100/hr budget.
- Which **browsers** are in use for the userscript (Chrome/Edge + Tampermonkey assumed).
- Whether the user wants the config file mirrored to `c:\data\configs` now or later.
