# SCRAPING_PROMPT.md — the autonomous brief

> **Hand the contents of this file to the next agent as its starting message.** It is self-contained: the
> agent must **not** need to ask the user anything. Every decision is either stated below or given a default
> in §9. If something is still ambiguous, pick the most reasonable option, write it down as an assumption in
> the work item's `RESULT.md`, and **keep going** — do not stop to ask.
>
> Companion docs, in read order: `AGENTS.md` (always-on) → `WORKFLOW.md` (read once) → this brief.

---

## 1. THE TASK (stated plainly — do not lose sight of it)

**Scrape every interesting Pokémon-card listing on finn.no into structured JSON, price each listing (and
each card where a description lists cards) through the PokeWallet API, and organize all of it into a
sortable table** where the estimated market value sits next to the seller's asking price, so the best deals
surface at a glance.

The finished state is a **working, resumable, tested pipeline plus the table(s)** — not a one-off script and
not a pile of half-wired modules. The search space is large ("thousands of ads"), so the pipeline must be
safe to stop, resume and re-run at any time.

Concretely, when you are done:
- every interesting finn.no ad has been **discovered** and **scraped** into structured data (+ images);
- every ad has a **parsed listing row**, and every ad that enumerates cards has **parsed card rows**;
- as many as the API budget allows have an **estimated market value in NOK** + the source it came from;
- all of it is joined into **table(s)** with a clear deal ratio;
- the whole thing is **proven** by committed tests and a coverage report.

You own the *how*. This brief fixes the *outcome* and the *constraints*, not the implementation. Find the
best solution yourself; prefer the simplest thing that is robust, resumable and verifiable.

## 2. How to operate (context discipline — mandatory)

- Read `AGENTS.md` (always-on bootstrap) and `WORKFLOW.md` **once**. That is your protocol: small
  self-contained `work/NNNN-*/` items, **success criteria + tests written first**, implement end to end,
  verify with real output, record evidence in `RESULT.md`, then the next item.
- **Do not read `PROJECT-PLAN.md` or `scraper-parser-spec.md` end-to-end.** Open only the section a task
  needs; the repo map in `AGENTS.md` §3 says where things live. Use `search_files` (grep) to jump.
- You are an **orchestrator of small items**, not one giant task. An item must be verifiable on its own and
  finishable in one context window. This program spans **many sessions**; leave the repo working and
  documented after every item.
- **Never use `ask_followup_question`.** If blocked (e.g. the API key is missing), do everything that is not
  blocked, mark the blocked part clearly, and report at the end — never halt the whole program.

## 3. The search intelligence (this is the "smart about queries" part)

The **canonical, machine-readable catalog of what Marius actually wants** already exists:

> **`finn/finn_searches.py`** — the single source of truth for the search set. Load it; **do not reinvent or
> hard-code** it. It defines `BROAD` phrases, `SETS` (tier 1 / tier 2) and `CARDS`, each with **aliases**
> (including common seller misspellings) and the exact FINN parameters, and it is consumable as a catalog
> (`uv run finn/finn_searches.py --list` / `--json`).
>
> The human origin of that catalog is **`prompts-notes/prompts.md`** (lines ~69–134) and
> **`prompts-notes/notes.md`**. Both are readable (prompts.md is **not** off-limits).

Current catalog, so you know the intent immediately (verify against the file — it is authoritative):

- **Broad phrases:** *Pokemon Kort · Pokemonkort · Vintage Pokemon Kort · Pokemon Samling · Pokemon Kort
  Holo · Japanske Pokemon Kort*. Also seen in notes: *"Vintage Samling 4570"* (4570 = a location-scoped
  search — include the location variant).
- **Tier-1 sets (wanted most):** Base Set (1999), Jungle (1999), Fossil (1999), Base Set 2 (2000),
  Team Rocket (2000), Gym Heroes (2000), Gym Challenge (2000), Neo Genesis (2000), Neo Discovery (2001),
  Neo Revelation (2001).
- **Tier-2 sets (wanted, "as long as they are at least 20 years old"):** Skyridge (2003), Base Set
  (1st Edition / Shadowless) (1999), Aquapolis (2003), EX Team Rocket Returns (2004), EX Deoxys (2005),
  EX Dragon Frontiers (2006), Expedition Base Set (2002), Neo Destiny (2002), EX Holon Phantoms (2006),
  Evolving Skies (2021).
- **Named cards:** Umbreon, Gengar, Mew, Mewtwo, Ho-Oh, Lugia, Pikachu, Jolteon, Alakazam, Rayquaza,
  Mightyena, Dragonair, Typhlosion, Raichu.
- **FINN parameters (verified):** `category=0.86`, `sub_category=1.86.285` (Samleobjekter),
  `product_category=2.86.285.396` (Samlekort). **Default sorts:** `PUBLISHED_DESC` + `RELEVANCE`.

**Query strategy (your job to make it excellent):**

1. **Load the catalog and run it** — broad phrases at 2 pages, Tier-1 sets first, then the named cards, then
   Tier-2 sets. Union across at least `PUBLISHED_DESC` and `RELEVANCE`; use `--all-pages` where a query is
   productive.
2. **Expand the catalog, version-controlled**, as you learn — you may *extend* `finn_searches.py`:
   - more seller typo/variant aliases for the named Pokémon and sets (typos are where deals hide);
   - Norwegian/English/Japanese spellings ("sjeldne pokemon kort", "japanske", "1st edition", "shadowless",
     "holo", "reverse holo", "psa", "graded", "sealed", "samling", "lot", "bundle");
   - the *era* the user cares about (WotC / vintage / 20+ years old) and related set names/abbreviations;
   - location-scoped variants (e.g. nearby postal codes) if useful.
3. **Deduplicate aggressively.** The FINN-kode is the primary key; the same ad across many queries must
   collapse to one row (the registry already supports this). Report `new` / `still-active` / `gone`.
4. **Rank by intent.** Tier-1 sets and named cards are the priority; use that ranking when deciding what to
   price first when the API budget is tight.

## 4. What already exists (reuse it, don't reinvent)

- `finn/finn_searches.py` — the search **catalog** (above), plus builders (`broad_defs`, `set_defs`,
  `card_defs`, `search_defs`, `catalog`) and a CLI (`--list`, `--json`, `--kind`, `--tier`).
- `finn/finn_search.py` — search **discovery**; decodes the server-rendered JSON (`docs` / `metadata` /
  `filters`); supports `--all-pages`, multiple `--sort`, `--param`, and a seen-kode **registry + delta**
  under `data/finn/searches/`. *Verify it consumes the catalog via `--search-set`; its `--help` currently
  shows only `-q`, so wire that integration if it is missing.*
- `finn/finn_ad.py` — one folder per ad under `data/finn/annonser/{kode}_{slug}/`: immutable raw HTML,
  parsed `{kode}.json`, max-resolution `photos/`, append-only `manifest.json`; global log
  `data/finn/_log/ad_scrapes.jsonl`.
- `finn/finn_matcher.py` — ad/heading → **ranked PokeWallet candidates + price**; append-only query cache
  `data/finn/_cache/query_cache.jsonl`; output `data/finn/matches/matches.jsonl`.
- (Referenced but **missing** — build it) **`finn/finn_identify.py`** — reuses `SETS` / `CARDS` to work out
  which *interesting* set/card an ad is. Needed to rank listings by Marius' intent.
- `pokewallet/pwlib/` — API client, budget handling, price extraction, set index, config, utils.
- `sheet/build_sheet.py` — turns local data into table payloads.
  **A Google Sheets MCP server may or may not be available:** if it is, publish there; if not, the local
  CSV/HTML in §10 **is** the deliverable. Do not block on Sheets.

Run everything with `uv run <script>.py`. Add dependencies only via the `uv-dependency-injector` skill.
When a module's behaviour is unclear, read its `--help` (they are detailed) or grep — do not read whole
large files.

## 5. The pipeline (stages, in order)

1. **Discover** — run the catalog (all kinds/tiers), all relevant pages/sorts; maintain the registry and
   delta report. (No API cost.)
2. **Scrape** — scrape every **new** FINN-kode into structured fields + max-size images (`--from-jsonl`),
   politely and resumably. (No API cost.)
3. **Identify** — for each ad, determine whether it matches an interesting set/card (build
   `finn_identify.py`); rank by intent. (No API cost.)
4. **Parse cards** — where the description enumerates cards (`Liste over kort:` …), structure them into
   per-card records with **provenance**. Reconcile title-vs-description counts and **flag** mismatches (a
   real example exists: a listing titled "79 stk" whose description says "99 stk" — surface it loudly,
   never silently pick one).
5. **Price** — match listings (and distinct parsed cards) to PokeWallet; record market value (NOK), source,
   FX rate, timestamp. Cache-first; budget-aware; resumable.
6. **Build the table** (§10).
7. **Report** — coverage counts + program report (§11).

## 6. Guardrails (non-negotiable — from `AGENTS.md` §4)

- **`uv run` only.** Never `python` / `pip install` / `uv pip install` / `uv run --with` / `uv run python`.
- **Never delete a file** — move it to a `.trash/` folder in the same directory. Raw pages, images,
  registries, matches, caches and logs are **append-only** and never mutated in place.
- **Never suppress errors.** Print counts and compare to expectations; mismatches are loud. No "success"
  printed without a check behind it.
- **Writes must fail rather than overwrite.** Idempotent and resumable by default.
- **Timestamps:** `%Y-%m-%d-%H%M%S`.
- **Git is read-only** unless the user asks.
- **Never edit a test to make it pass.** A red test is a finding — report it (`WORKFLOW.md` §4).
- **Never modify the user's rules** (`~/.roo/rules/**`) or `AGENTS.md`'s rule sections; propose changes.
- **API budget is shared:** **100 requests/hour, 1000/day**, and cached responses still count. Never spend
  the last ~10/hour — reserve them. On exhaustion: stop cleanly, record state, resume next window.
- **Never commit the API key.** Read it from the `API_KEY_POKEWALLET` env var.
- **Be polite to finn.no:** delays + jitter between requests, modest volume, personal use. FINN's footer
  discourages systematic scraping — keep it low-frequency and efficient (search first, then only new ads).

## 7. Budget reality (read this or you will fail)

You cannot price thousands of cards in one hour. Design for **breadth first, depth over time**: discovery,
scraping, identification and card-parsing cost **no API calls** and should complete first; pricing then runs
across hourly windows, prioritising Tier-1 / named-card listings and distinct cards not yet in the cache.
Because the matches file and query cache are append-only and cache-first, **every session makes durable
progress** and re-running is cheap. Ship a working, resumable pipeline that keeps improving — **never fake
completeness.**

## 8. Autonomy & research

You are expected to **figure things out** rather than ask. That includes:

- Reading the existing modules, their `--help`, and the relevant spec sections to understand how the pieces
  fit. You may read `prompts-notes/` (including `prompts.md`).
- Researching FINN's search behaviour/parameters when useful (the embedded JSON already exposes the full
  filter map — prefer that over guesswork), and PokeWallet's API via `docs/`.
- Choosing the simplest robust design, and **recording every assumption** in `RESULT.md`.
- Extending the catalog, adding tests/fixtures, and refactoring for clarity — as long as you keep the
  guardrails and leave evidence.

Do **not** ask the user questions. Decide, document, proceed.

## 9. Decisions already made (defaults — do NOT ask)

- **Search set:** loaded from `finn/finn_searches.py`; extend it with typo/variant/era/language aliases.
- **Priority:** Tier-1 sets → named cards → Tier-2 sets → broad phrases.
- **Price source:** primary = TCGPlayer `market_price`; fall back to CardMarket (`trend`, then `avg`).
  Store **both** when present, plus which was chosen.
- **Currency:** market value converted to **NOK**; store the FX rate and its date. Asking price is NOK.
- **Deal ratio:** `market_value_nok / asking_price_nok`. Never blend the FINN asking price into the
  market-price column.
- **Cadence:** price as often as the budget allows (protect a ~10/hour floor); never re-price a fresh cached
  value.
- **Politeness:** base delay ~1.0 s + random jitter; stop-and-resume rather than burst.
- **Card list:** extract only when the text enumerates cards; otherwise `card_list_present = false`.
- **Google Sheet:** publish only if an MCP server is available; otherwise the local CSV/HTML table is final.
- **Ambiguity:** choose the most reasonable option, record it as an assumption, proceed.

## 10. The table (the deliverable)

Local, append-only source of truth **plus** generated, human-usable table(s):

- **Source of truth (append-only):** the per-ad archives under `data/finn/annonser/`, the registries/logs
  under `data/finn/`, and `data/finn/matches/matches.jsonl`.
- **Generated tables** under `data/finn/tables/`, timestamped, with a `latest` copy:
  - **Listings table** — one row per FINN-kode: identity, url, title, asking price, status
    (Aktiv/Inaktiv/Solgt), location, image count, matched interesting set/card, parsed-card count, matched
    PokeWallet card(s), market value (NOK) + source, FX rate, **deal ratio**, timestamps, coverage/freshness
    flags.
  - **Cards table** — one row per parsed card: parent FINN-kode, card name, set/variant hints, count,
    matched PokeWallet id/name, market value, provenance.
- Emit as CSV (and a self-contained HTML table if cheap). **You define the exact schema** — make it
  sortable, self-explanatory, and keep machine-read vs derived vs human columns clearly separated.

## 11. Definition of Done (program)

- [ ] Committed tests pass; the harness covers parsing + identify + matcher + table build with real fixtures.
- [ ] Discovery ran the full catalog; the registry reports `new` / `still-active` / `gone` totals.
- [ ] Every discovered ad has been scraped, or is on a visible, resumable "todo" list with reasons.
- [ ] Card lists are structured where present, with provenance and title-vs-description mismatches flagged.
- [ ] Pricing is cache-first and resumable; coverage reported (ads priced / total, cards priced / parsed).
- [ ] The table(s) build from local data and open cleanly; columns show asking price vs market value +
      deal ratio.
- [ ] A program report (`work/<id>/RESULT.md` + a short summary in `work/`) states: counts, commands, the
      exact point to **resume** from, and every assumption made.
- [ ] Nothing was deleted; all failures visible; no unverified "success".

## 12. Resume protocol (this program spans sessions)

- Every item writes `work/<id>/TASK.md` (success criteria + tests) and `work/<id>/RESULT.md` (evidence,
  status, assumptions, exact resume point). Keep `work/_index.md` up to date.
- On a fresh session: read `AGENTS.md` → `WORKFLOW.md` → `work/_index.md` → the in-progress item's
  `TASK.md`/`RESULT.md`, then continue. **Never restart the program from scratch.**
- After a context compaction mid-item: re-read your `TASK.md` and `RESULT.md` — they are the source of truth.
