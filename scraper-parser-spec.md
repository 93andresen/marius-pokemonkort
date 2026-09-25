# Scraping → Spreadsheet Pipeline: Additional Instructions & Suggestions

> **Origin:** grew out of the original human-written brief [`prompts-notes/scraper-parser-spec-prompt.md`](prompts-notes/scraper-parser-spec-prompt.md). That brief is superseded by this spec — kept only as history (nothing is ever deleted). We are starting from scratch here: nothing is based on the older spreadsheet/tracker docs, though links to relevant repo context are kept below.
>
> **Relevant context already in the repo:**
> - Google Sheet: `13TfMos8hP4zT3-Tf92F7ZE0hJ2r7cKJdEqvdj0gvtpM` (see [`prompts-notes/notes.md`](prompts-notes/notes.md))
> - Older spreadsheet tab architecture (pre-pivot, reference only): [`pokewallet-api-ideas/pokemon-card-collection-tracker-plan.md`](pokewallet-api-ideas/pokemon-card-collection-tracker-plan.md)
> - Sample scraped ads (pre-pivot captures, now archived): [`.trash/finn/annonser/Pokemon_kort/Pokemon_kort.md`](.trash/finn/annonser/Pokemon_kort/Pokemon_kort.md)
> - Scraper tool: `C:\data\code\93andresen_Scripts\web_to_md.py` (run with `uv run`, use `--js`)

---

## 0. Non-negotiable principles (the philosophy everything else follows)

1. **We never delete anything. Ever.** This applies to the entire repo, in every sense. Removal from the working tree means moving to `.trash/`, and history is version-controlled. The pipeline itself is effectively an **append-only log**: we can always go back and see what was, and no information is ever lost.
2. **Scraped sources are immutable.** What we scrape from the internet is a *source*. We can run whatever tools we want on it and output whatever we want from it, but sources are never edited. Fix something, improve the parser? Re-run it on the sources — they are always there, unchanged.
3. **Version the producer, version the output.** The parser is versioned, and every output row records the `parser_version` that produced it. When the parser is updated we may re-run it on sources, but we do not silently rewrite old values — a human may be referencing the data, and if a value changes, that change must be visible as history, not a silent mutation.
4. **"Save everything" means there is no progress point to lose.** Every completed capture is durable the moment it is written. A crash mid-batch leaves a partial but valid archive — nothing is lost. What people usually call "checkpoints" (§4.4) exist only to avoid *re-requesting* the same URLs (politeness/efficiency), never to protect data.
5. **Machine-read stays machine-read, humans stay in their own columns** — the two-kinds-of-data rule (§2.0). Writers never touch columns owned by other writers.

---

## 1. Scraping mechanics

### 1.1 URL handling & canonical IDs
- [ ] Always canonicalize every FINN link to its **FINN-kode** (the numeric ad id, e.g. `475878513`). The FINN-kode is the **primary key** for everything: folders, spreadsheet rows, dedupe, image downloads.
  - Accept all input forms: share-link (`finn.no/475878513`), address-bar link (`/recommerce/forsale/item/475878513`), image deep-link (`...?ci=20`), and search-result links.
  - Regex-extract the kode, ignore the rest of the URL. Never create two entries for the same ad because the URLs looked different.
- [ ] Detect and flag **duplicates and relistings**: same seller + same title + similar photos but a *new* FINN-kode = probably a relist. Track both kodes and link them.

### 1.2 Images
- [ ] **Max resolution is mandatory.** The scraped md contains thumbnail URLs (`/dynamic/142w/...`) and medium gallery URLs (`/dynamic/960w/...`). Never download those. Transform every image URL to the largest known size (`/dynamic/1280w/...` — verify whether even larger prefixes like `1600w`/`original` exist by testing one ad).
- [ ] Derive image URLs from the **UUID pattern**, not from clicking through the gallery: `https://images.finncdn.no/dynamic/{SIZE}/item/{itemRef}/{uuid}`. One scrape of the ad page yields all UUIDs → all images can be downloaded in one pass, no `?ci=N` loop needed.
- [ ] Download images into the ad's own folder: `photos/01.jpg, 02.jpg, ...` (zero-padded, ordered by original gallery order).
- [ ] Record in the spreadsheet/log: number of images downloaded vs. number of images in the gallery. Any mismatch = failed download = visible error (no silent partial success).
- [ ] Verify image integrity (non-zero file size, correct content-type), not just HTTP 200.
- [ ] Keep the image **UUID in a manifest file** (or spreadsheet column) so re-scrapes can skip already-downloaded images (idempotent, resumable).

### 1.3 Raw capture policy
- [ ] Always scrape with `--js` (Block B is a strict superset of Block A and adds: favorite count, "Send melding", expand button, breadcrumbs, high-res gallery). Block A is never enough.
- [ ] Raw `.md` captures are **immutable archives** — never edit them after scraping. All cleaning/parsing happens downstream. If a parse bug is found later, re-parse the same raw file.
- [ ] Capture and store **scrape timestamp** separately from the ad's own "Sist endret" timestamp. Both go into the spreadsheet.
- [ ] Detect and record ad **status** at scrape time: `Aktiv` / `Inaktiv` / `Solgt` — status is as valuable as price (see §3.4 comps).

### 1.4 Folder structure
- [ ] One folder per ad, keyed by FINN-kode so the structure is stable even if the title changes:
  ```
  finn/annonser/{FINN-kode}_{url-slug-of-title}/
      {FINN-kode}.md          ← raw JS-rendered capture
      photos/01.jpg ... NN.jpg
      manifest.json (optional)  ← scrape metadata: url, timestamp, image list
  ```
- [ ] Folder names must never collide: if two ads have the same slug, the kode prefix guarantees uniqueness.

### 1.5 Search-page scraping (discovery)
- [ ] Build the **complete parameter map** of finn.no search (as required in the base file): every sort value (`PUBLISHED_ASC/DESC`, `PRICE_ASC/DESC`, `RELEVANCE`, `CLOSEST`), `q`, `sub_category=1.86.285` (Samleobjekter), `product_category=2.86.285.396` (Samlekort), `stored-id`, `lat`/`lon`, `polylocation`, page offset, price range filters, and every filter exposed in the UI. Store it as a reference doc + a machine-readable list.
- [ ] **Pagination**: scrape all pages of a search, not page 1. Detect the last page and verify the ad count matches (again: visible verification, not silent truncation).
- [ ] **Delta detection**: keep a registry of all FINN-kodes ever seen per search query. Each run reports: new ads / still-active known ads / gone (sold or removed) ads. New ads are the trigger for full ad-scrapes.
- [ ] Scrape each search with **at least two sorts** (`PUBLISHED_DESC` for freshness, `RELEVANCE` for recall) and union the results — cheap insurance against ranking-dependent omissions.
- [ ] Vary the query list systematically: "pokemon kort", "vintage pokemon kort", "pokemon samling", set names like "Base Set Charizard", "japanske pokemon kort", misspellings that sellers make, e.g. "pokémon", "pok mon", "poekmon"). Seller typos are where underpriced deals hide.
- [ ] Keep a **scrape log** (timestamp, URL, result, error) — append-only, same principle as the price history in the spreadsheet plan.

### 1.6 Politeness, limits, legal
- [ ] Rate-limit all requests (delay between requests, randomized jitter). The system must be runnable daily without stressing finn.no.
- [ ] Be aware: FINN's footer explicitly prohibits systematic scraping without written permission. Keep volume modest, personal-use, and low-frequency. Design the pipeline to be efficient (search pages → only new/changed ads get full scrapes) rather than brute-force.
- [ ] Retry with backoff on transient failures; cap retries; log every failure. A failed scrape must end up in a visible "failed" list, never silently dropped.

---

## 2. The scraper & parser: exact behavior and the data-ownership rule

### 2.0 The rule: two kinds of data

This is a rule about **columns/fields across the whole system** (parser output, staging CSV, spreadsheet columns) — it decides *which writer may fill which column*, and what happens on a re-scrape. There are only two kinds:

| Kind | What it is | Who writes it | On re-scrape / re-run |
|---|---|---|---|
| **Machine-read** | Read directly off the page by anchored extraction (regex/structural match — it either matches or it's MISSING) | Parser only, **append-only** | Each scrape **appends** new values; existing rows are never touched |
| **Derived** | Anything **not strictly machine-read**: LLM interpretation/estimates, and human-entered data | LLM → its own clearly-labeled columns (with provenance); humans → ordinary manual columns | LLM columns: regenerated by re-running; **human columns: NEVER written by automation** |

The single non-negotiable invariant behind the table: **a writer never touches a column owned by another writer.**
- This is what protects manual work: if you edit a cell by hand, it must be in a column the scraper and the LLM never write to — so it can never be silently reverted.
- Symmetrically, machine-read values must never be hand-edited: the next scrape appends a fresh row anyway, so a hand edit just creates a silent contradiction between the sheet and the raw archive.
- No column mixes kinds: a "price" column that sometimes holds the seller's number and sometimes the LLM's estimate is the exact failure mode this rule exists to prevent.

### 2.1 Machine-read fields, with exact extraction anchors

Grounded in the real captures (`.trash/finn/annonser/tests/image-20-js.md`, `.trash/finn/annonser/Pokemon_kort/Pokemon_kort.md`, `.trash/finn/annonser/Pokemonkort_-_79_stk_reverse_holo/Pokemonkort_-_79_stk_reverse_holo.md`):

| Field | Anchor in raw `.md` | Notes |
|---|---|---|
| `finn_kode` | `Sist endret: ... ・ FINN-kode: NNN` | Cross-check against `adId=` in the map URL — two independent anchors, must agree |
| `title` | First `# ` heading after `## Bildegalleri` | |
| `status` | Literal line immediately after title: `Solgt` / `Inaktiv` / (absent = Aktiv) | |
| `price_nok` | First `NNN kr` under `## Til salgs` — **first match only** | Must NOT pick up prices from "Mer som dette" (similar ads) further down |
| `shipping_nok` | `Frakt fra NNN kr` | Only present sometimes; absence is itself data |
| `trygg_betaling_nok` | `+ Trygg betaling NN kr` | Same |
| `condition` | `Tilstand: **...**` | Seller's own claim — machine-read as *raw text*; what it *means* for value is not |
| `lat` / `lon` / `postal_code` | Query params of the map link (`adId=...&lat=...&lon=...&postalCode=...`) | Fully deterministic — never geocode by place name |
| `location_text` | Link text of the map link (e.g. `2008 Fjerdingby`) | |
| `last_modified` | `Sist endret: D.M.YYYY kl. HH:MM` | Norwegian date format; convert deterministically |
| `favorite_count` | Regex `(\d+)Legg til som favoritt` after the gallery | JS capture only — one more reason `--js` is mandatory |
| `image_uuids` / `item_ref` | Gallery URLs `/dynamic/{size}/item/{item_ref}/{uuid}` | |
| `gallery_count` | `(n/m)` in the gallery header | Cross-check: m == number of UUIDs |
| `breadcrumbs` | Links under `## Her er du` | |
| `fiks_ferdig` | Literal `Fiks ferdig` / truck icon near price | |
| `description_raw` | Text between `## Beskrivelse av varen` and the map link | Immutable blob; its *contents* are not interpreted at this stage |
| `card_list_raw` | Lines between `Liste over kort:` and `Pluss tegn` | Immutable blob; structuring it is LLM-derived (§2.3) |

Parser rules for machine-read fields:
- [ ] **Anchor-based only.** Every field has exactly one defined extraction anchor. If the anchor doesn't match (FINN changed layout), the field is `MISSING` — never a heuristic fallback, never a guess, never an LLM "filling it in".
- [ ] **Cross-check where two anchors exist** (FINN-kode vs `adId`; gallery count vs UUID count). A mismatch is a loud error, not a silent pick of one.
- [ ] **Append-only.** Each scrape event appends a Tier A row with `scraped_at`. Values are never mutated in place.
- [ ] **Beware capture-position traps:** prices from the "Mer som dette" similar-ads section are a different entity (see §5) and must never land in the ad's own `price_nok`.
- [ ] `parse_quality` per scrape: `full` / `partial` / `failed` — derived deterministically from which anchors matched.

### 2.2 Machine-read derivations (still just machine-read)

- [ ] Simple computations over machine-read fields are **still machine-read** — same writer (parser/formula), same immutability, no separate category needed:
  - `total_cost_nok = price + shipping + trygg_betaling` (a MISSING input propagates as MISSING, never assumed 0).
  - `scraped_age_days`, `modified_to_scraped_gap` — date math over scraped dates.
  - `price_per_image` and similar ratios depending only on scraped fields.
- [ ] Anything needing `card_count` is NOT machine-read — card count requires interpretation. See §2.3.

### 2.3 Derived: LLM interpretation (NOT POSSIBLE without an LLM)

- [ ] **Card list structuring:** `card_list_raw` (plain names like "Venusaur", "MewTwo", "Darkness Energy") → per-card records (name, set guess, variant hints, count). The set is genuinely ambiguous from the name alone; the ad's own legend ("S - Shaddowless Base set, R - Reverse holo") is machine-read *text* whose mapping onto each line is LLM-derived.
- [ ] **Condition-code legend parsing:** NM/LP/MP/HP/DMG mappings defined inside descriptions.
- [ ] **Count reconciliation — flag, never resolve:** real example in this repo — the ad titled "79 stk reverse holo" says "**99** stk" in its description. Detecting that mismatch is deterministic (compare scraped title tokens vs description tokens); *deciding* which is true is a human call. The system's job is to surface the discrepancy loudly.
- [ ] **Valuation & deal score:** structured cards → PokeWallet IDs → value → `value_ratio` vs asking price. All outputs are estimates with provenance.
- [ ] **Storage contract for every LLM-derived output:** `input_excerpt` (the machine-read text it came from), `method` (model + version), `confidence`, `produced_at`, and it must be **reproducible** (re-running the same method on the same input gives the same output). LLM-derived values are regenerated by re-running, never hand-edited.
- [ ] If no LLM pass has run for an ad, these fields are `NOT_DERIVED` — a visible state, not a blank.

### 2.4 Human columns — not part of the scraper/parser contract at all

- [ ] `interest` (ignore/watch/contact/negotiating/bought), buy decision, `notes`, condition judgment from photos, seller trust, the final "is this deal real" call.
- [ ] These are just ordinary manual spreadsheet columns. The only rules: **automation never writes to them** (so manual edits can never be reverted), and they may *reference* scraped/LLM values but never overwrite them. When you buy an ad, the decision lives here and links into `Purchases`.

### 2.5 Write-access summary (who writes what)

| Writer | May write |
|---|---|
| Parser (per scrape) | Machine-read columns, append-only (incl. machine-read derivations) |
| Formulas | Machine-read derivations |
| LLM passes | LLM-derived columns only, with provenance |
| Human | Manual columns only |
| Nobody, ever | Machine-read values after the scrape event that produced them |

### 2.6 Photo-based extraction — **FUTURE PLANS, NOT FOR IMPLEMENTATION YET** (kept in mind for later)
> Status: idea parked for the future. Nothing in the current pipeline should build this; design decisions (folder structure, image archives) just shouldn't block it later.
- [ ] Many ads have **no card list in the text** — the cards are only visible in photos. A future **vision/LLM pass over the photos** could: identify visible cards, count them, detect holo/reverse-holo/graded/1st-edition markers, and detect condition signals (sleeves, binders, visible damage).
- [ ] Output of the vision pass would be **LLM-derived** (interpretation with provenance), stored per ad (not overwritten), feeding the same valuation flow as the text card list.
- [ ] This is what would eventually enable the killer metric: **true kr-per-card** and **estimated total card value vs. asking price** for bulk lots.

---

## 3. Spreadsheet ingestion (Google Sheets via MCP)

### 3.1 Data flow
- [ ] Pipeline: `raw md archive → parser → staging (local md/csv) → Google Sheets`. The spreadsheet is a *view + ledger*, the raw files are the source of truth. This mirrors the plan doc's "sheet is source of truth for ownership; external source for facts" split.
- [ ] Two-layer tabs (matching the append-only principle from the plan doc):
  - **`FinnAdsRaw`** — append-only: one row per scrape event per ad. Never updated, only appended. Includes scrape timestamp and full parsed fields.
  - **`FinnAdsCurrent`** — one row per ad, the latest known state. Rebuilt/upserted from Raw.
- [ ] Never overwrite history in Raw; "price went from 900 → 700 kr" must be visible as two rows, not one mutated cell.
- [ ] Every column in every tab is tagged with its kind (§2): machine-read / LLM-derived / manual. **Machine-read columns are write-protected from humans; only manual columns (`interest`, `notes`, condition judgment) accept hand edits.** LLM-derived values live in clearly-labeled separate columns/tabs so an estimate can never be mistaken for a scraped fact.

### 3.2 Core ad table schema (additions to what the base file implies)
- [ ] Columns: `finn_kode` (key), `url`, `title`, `price_nok`, `shipping_nok`, `total_cost_nok` (price + shipping + trygg betaling), `condition`, `location`, `postal_code`, `seller_ref`, `favorite_count`, `fiks_ferdig`, `status`, `published`, `last_modified`, `first_seen`, `last_seen`, `image_count`, `folder_path`, `description_extract`, `card_list_present`, `parsed_card_count`, `deal_score`, `notes`.
- [ ] Kind tagging on those columns: machine-read = scraped facts (`title`, `price_nok`, ...); machine-read derivations = `total_cost_nok`, `image_count`; LLM-derived = `parsed_card_count`, `deal_score`; manual = `notes`, `interest`.
- [ ] `deal_score` / `value_ratio` (formula-driven from Tier C valuations): estimated card value ÷ asking price, and kr-per-card. Even a rough estimate makes the sheet sortable from "all ads" → "best opportunities first", which is the actual point of the whole system.

### 3.3 Dedupe & integrity
- [ ] `finn_kode` is unique in `FinnAdsCurrent`; enforced with data validation / conditional-format duplicate highlighting.
- [ ] Error-checking rules per the universal "no silent success" principle: a formula flags rows where `image_count ≠ photos on disk`, where required fields are MISSING, or where the balance of parsed card counts doesn't add up.
- [ ] Currency is always NOK on finn.no, but record the FX date if valuations come from EUR/USD sources (CardMarket/TCGPlayer) — needed for honest deal scoring.

### 3.4 Sold-ad intelligence (comps — a suggestion not in the base file)
- [ ] **Keep scraping inactive/sold ads.** Sold ads are historical sales data: they tell you what actually sells, at what price, and how fast. Over time this builds a finn.no price history for vintage sets that no price API covers.
- [ ] Track **time-to-sell** (`published` → `status != Aktiv` first observed). Velocity per category is a direct input into the arbitrage model in [`prompts-notes/old/research-prompt-pokemon-arbitrage-norway.md`](prompts-notes/old/research-prompt-pokemon-arbitrage-norway.md) ("a 10% margin that takes 6 months is worse than a 5% margin in a week").
- [ ] Track **favorite count over time** as a demand signal (JS-only field — another reason `--js` is mandatory).

### 3.5 Sheets UX
- [ ] Conditional formatting: highlight new ads, price drops, sold transitions, rows with MISSING fields.
- [ ] Data validation dropdowns for the manual columns: `status`, `interest` (ignore/watch/contact/negotiating/bought), condition judgment.
- [ ] A manual **`interest`/pipeline column** is essential: the sheet is not just a monitor, it's a buying decision tracker (seen → contacted → offered → bought). Add a `FinnPurchases` linkage so a bought ad flows into the existing `Purchases`/`BulkAllocation` tabs from the plan doc — closing the loop from *scrape* → *deal evaluation* → *purchase ledger*.
- [ ] Config tab entries for the scraper: base URLs, search query list, scrape frequency, max requests per run, folder root.

---

## 4. Suggestions not yet mentioned anywhere

1. **Notification layer.** New-ad detection should optionally push a summary (e.g. to console/log first; later Telegram/email) — "3 new pokemon-kort ads since last run, best deal: X at 45% of est. value". The system "predicts intent instantly" only if you don't have to open the sheet to learn something happened.
2. **Seller dimension.** Power sellers (card shops flipping lots) deserve their own small tab: ad history, typical markup, average time-to-sell. Knowing the sellers is as useful as knowing the ads.
3. **Snapshot the search result page itself** (not just ads): the raw search md is evidence of what existed at time T. By principle §0.1 this is not even a choice — everything is saved, always. Kept here as a reminder of *why*: priceless for debugging "why didn't we see ad X".
4. **Avoid re-requesting completed scrapes in a batch.** (Rephrased from "resume/checkpoint": per principle §0.4 there is no data progress point to lose — every finished capture is already saved. A record of completed FINN-kodes only prevents wasting requests on URLs we already have, which is a politeness/efficiency concern, not a data-safety one.)
5. **Version the parser.** Raw md is immutable, but parsing rules will evolve. Store `parser_version` per row so old rows can be re-parsed and improvements measured — and so old outputs are never silently rewritten (principle §0.3).
6. **Price-change alerts within an ad** (seller lowers price) — historically the strongest buy signal on marketplaces.
7. **Cross-check against Cardmarket/TCGPlayer in one direction only:** finn prices are NOK asking prices; API prices are market values. Store both with their currencies and let `deal_score` do the comparison — never blend currencies in one column.
8. **Local CSV export backup** of the whole sheet on each run (the sheet is a Google service; a daily CSV snapshot in the repo is free insurance against accidental edits).
9. **Test fixtures.** Keep a couple of raw ad captures (active + sold + weird-format) as fixed test inputs so parser changes can be verified instead of eyeballed — aligned with "verify, don't claim success".
10. **Cost-of-acquisition memory:** when an ad is bought, backfill its `finn_kode` into `Purchases` so later "how did this lot perform?" questions can be answered from the original ad (photos, description, favorite count).

---

## 5. Open questions (ask, don't assume)
- What is the actual maximum finncdn image size (`1280w` confirmed; does `original`/`1600w` work)?
- Does the search result page expose total result count that we can assert pagination against?
- How often should the system run (daily? on-demand only?), and is there a request budget ceiling we should hard-code?
- Should inactive ads be auto-archived to a separate tab after N days to keep `FinnAdsCurrent` fast?
- **ANSWERED (discussed 2026-09-25):** Should the "Mer som dette" (similar ads) listings on ad pages be harvested as a discovery source? → **Not as a discovery source** — we will not have a problem finding pages to scrape. Interesting to think about how FINN's similarity algorithm picks them, though. And because raw ad captures are saved whole (§0.1), the "Mer som dette" section is already inside every raw capture anyway — the data exists if we ever want it, at zero extra cost.
