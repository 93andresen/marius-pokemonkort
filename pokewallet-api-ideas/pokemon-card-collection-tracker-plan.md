# Pokémon Card Collection Tracker — Spreadsheet Design Plan

> **Version:** 1.0 · **Date:** 2026-08-20 · **Status:** Design draft, ready for implementation
>
> **Target:** Google Sheets (via Google Sheets MCP) · **Data source:** [PokeWallet API](https://api.pokewallet.io) (docs at [`docs/pokewallet_io_api-docs.md`](pokewallet_io_api-docs.md))
>
> **API Key:** `API_KEY_POKEWALLET` (free plan: **100 req/hour · 1000 req/day**)

---

## Table of Contents

1. [Goals & Requirements](#1-goals--requirements)
2. [What We Learned From the API (tested live)](#2-what-we-learned-from-the-api-tested-live)
3. [Design Principles](#3-design-principles)
4. [Spreadsheet Architecture — Tab Overview](#4-spreadsheet-architecture--tab-overview)
5. [Detailed Tab Schemas](#5-detailed-tab-schemas)
   - 5.1 [`Cards` — Master Collection Registry](#51-cards--master-collection-registry)
   - 5.2 [`Purchases` — Acquisition Ledger](#52-purchases--acquisition-ledger)
   - 5.3 [`BulkAllocation` — Bulk Purchase Cost Spreading](#53-bulkallocation--bulk-purchase-cost-spreading)
   - 5.4 [`PriceSnapshots` — Price History](#54-pricesnapshots--price-history)
   - 5.5 [`Prices` — Current Prices Cache](#55-prices--current-prices-cache)
   - 5.6 [`Sets` — Set Reference](#56-sets--set-reference)
   - 5.7 [`CardCatalog` — API Card Reference Cache](#57-cardcatalog--api-card-reference-cache)
   - 5.8 [`RateLog` — API Usage Tracker](#58-ratelog--api-usage-tracker)
   - 5.9 [`Config` — Settings](#59-config--settings)
   - 5.10 [`Dashboard` — Overview](#510-dashboard--overview)
6. [Bulk Purchases — Deep Dive](#6-bulk-purchases--deep-dive)
   - 6.1 [Why allocation matters](#61-why-allocation-matters)
   - 6.2 [Method A: Equal split](#62-method-a-equal-split)
   - 6.3 [Method B: Fair-market-weight allocation](#63-method-b-fair-market-weight-allocation)
   - 6.4 [Method C: Bulk-rate + residual method](#64-method-c-bulk-rate--residual-method)
   - 6.5 [Method D: Manual / known prices](#65-method-d-manual--known-prices)
   - 6.6 [Method E: Lot-level tracking (no per-card split)](#66-method-e-lot-level-tracking-no-per-card-split)
   - 6.7 [Recommendation & worked example](#67-recommendation--worked-example)
   - 6.8 [Packs & sealed products](#68-packs--sealed-products)
7. [Price Tracking Over Time](#7-price-tracking-over-time)
8. [Rate Limit Budget & Strategy](#8-rate-limit-budget--strategy)
9. [Adding Cards — Workflows](#9-adding-cards--workflows)
   - 9.1 [Individual card entry](#91-individual-card-entry)
   - 9.2 [Scanner app exports](#92-scanner-app-exports)
   - 9.3 [Import pipeline design](#93-import-pipeline-design)
10. [Google Sheets Implementation Notes](#10-google-sheets-implementation-notes)
11. [Dashboards & Views](#11-dashboards--views)
12. [Implementation Roadmap](#12-implementation-roadmap)
13. [Open Questions & Decisions Needed](#13-open-questions--decisions-needed)
14. [Appendix: Key Formulas](#appendix-key-formulas)

---

## 1. Goals & Requirements

The tracker must answer, for **every physical card** in the collection:

| Question | Where it's answered |
| --- | --- |
| What card is it, exactly? (set, number, variant, language, condition) | `Cards` tab |
| How many copies do I own? | `Cards.qty` |
| What did I pay for it? | `Purchases` + `BulkAllocation` |
| What is it worth right now? | `Prices` / `PriceSnapshots` (from API) |
| How has the price changed over time? | `PriceSnapshots` history + CardMarket `avg7`/`avg30`/`trend` |
| What's my profit/loss per card? | computed on `Dashboard` |
| Where is it stored? | `Cards.location` |
| Which set/rarity/type do I have? | `Sets`, `Cards` |

**Additional requirements:**
- Support **individual card entry** (typing a card name, auto-fetching data from API).
- Support **scanner app exports** (bulk CSV/Excel imports from apps like Collectr, TCGplayer app, DragonShield, etc.) — design must accept imperfect external data and dedupe.
- Support **bulk purchases** (lots, binders, "79 reverse holo" type deals) where the total price must be split across many cards.
- Track **price paid** separately from **current value** so profit/loss is real.
- Stay **within API rate limits** (100/hr, 1000/day) with a visible budget.
- Works entirely through Google Sheets MCP — tabs, formulas, and (later) Apps Script for automation.

---

## 2. What We Learned From the API (tested live)

All of the following was **verified with the actual API key** on 2026-08-20.

### 2.1 Endpoints that work on the free plan ✅

| Endpoint | Use | Notes |
| --- | --- | --- |
| `GET /search?q=...` | Find cards by name, set code, or `set_id + card_number` | Returns **full pricing** for TCGPlayer + CardMarket. `q=1464 107` = precise lookup (set_id + card number). Cached 15 min. |
| `GET /cards/:id` | Get one card's full detail + pricing | Works with `pk_...` (TCG) and bare hash (CardMarket-only) IDs. Cached 60 min. |
| `GET /sets` | List **all** sets (~150) | Gives `name`, `set_code`, `set_id`, `card_count`, `language`, `release_date`. Cached 120 min. |
| `GET /sets/:setCode` | List cards in a set (paginated) | **Prices arrays are empty** in set listing — only metadata + product URLs. Use for building the card catalog, not for prices. |
| `GET /images/:id` | Card image | Available with key. |
| `GET /health`, `GET /` | Health / API info | No auth needed. |

### 2.2 Endpoints blocked on the free plan ❌ (all return `403 "Trial not activated"`)

| Endpoint | What we lose | Why it matters |
| --- | --- | --- |
| `GET /prices/:setCode` | **All prices for an entire set in ONE request** | This would be the holy grail for rate limits (1 request = whole set's prices). **Blocked.** |
| `GET /cards/:id/price-history` | Official 7/14/30/60/120-day price history | Blocked → we must build our own history via snapshots. |
| `GET /sets/:setCode/statistics` | Set-level avg/min/max prices | Blocked. |
| `GET /sets/trending`, `/sets/:setCode/completion-value`, `/analytics/top-cards` | Discovery / set completion cost | Blocked. |

> **Key design consequence:** on the free plan, fetching prices costs **1 request per card** (via `/search` or `/cards/:id`). The only way to get *whole-set* pricing in one call (`/prices/:setCode`) is the **Pro plan (€20/month)** or the **7-day free trial**. This heavily shapes the rate-limit strategy in [§8](#8-rate-limit-budget--strategy).

### 2.3 What the price payloads look like (verified)

**TCGPlayer** (per variant, identified by `sub_type_name`: `Normal`, `Holofoil`, `Reverse Holofoil`, `1st Edition`, `Unlimited`, `Shadowless`):
```
low_price, mid_price, high_price, market_price, direct_low_price, updated_at
```

**CardMarket** (per variant, `variant_type`: `normal` or `holo`):
```
avg, low, avg1, avg7, avg30, trend, updated_at
```
> `avg7` = 7-day moving average, `avg30` = 30-day average, `trend` = current trend price. **This is free trend data we get on every request** — great for "price changes over time" without Pro.

### 2.4 Card ID formats

- **TCG cards:** `pk_` + long hex hash (these also carry CardMarket data when available).
- **CardMarket-only cards:** bare hex hash (Japanese sets, EU promos, V1–V7 variants share `card_number` but have unique IDs).
- **Consistent set identifiers:** every card carries `set_id` (numeric group id) and `set_code`. `set_id + card_number` is the **precise search key**.

### 2.5 Rate limit headers (verified on real responses)

```
X-RateLimit-Limit-Hour: 100
X-RateLimit-Remaining-Hour: 95
X-RateLimit-Limit-Day: 1000
X-RateLimit-Remaining-Day: 823
```
> Important: **cached responses (`X-Cache: HIT`) still decrement the quota** (verified). So caching helps latency, not quota.

---

## 3. Design Principles

1. **One row = one physical card identity** in `Cards`, but quantities live in a column (a playset is 1 row with `qty=4`). Cost basis per copy is tracked in `Purchases`/`BulkAllocation` with quantities, so per-copy cost math stays correct.
2. **Never overwrite history.** Price history is *append-only*. The `Prices` tab is a *cache* (current snapshot); `PriceSnapshots` is the *record*.
3. **Everything joins on stable IDs.** Cards are keyed by the **PokeWallet card ID** (`api_card_id`) + variant. Set joins use `set_id`. Never match on display names alone.
4. **The sheet is the source of truth for what you own; the API is the source of truth for what cards exist and what they cost.** Manual columns (`paid`, `condition`, `location`, `notes`) are yours; API-derived columns (`name`, `set`, `prices`) are refreshable.
5. **Bulk allocation is explicit and auditable.** Every bulk purchase gets a documented allocation method (`BulkAllocation.allocation_method`), so "why did this Charizard cost 45 kr?" is always answerable.
6. **Rate limits are a first-class concern.** Every API call is logged (`RateLog`) and budgeted.
7. **Inputs are tolerant.** Scanner exports are messy → import maps fuzzy names → `api_card_id`; anything unresolvable lands in an `Unresolved` review list, never silently dropped.

---

## 4. Spreadsheet Architecture — Tab Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         Dashboard (view-only, formulas)                    │
│   KPIs · Charts · Top movers · Set completion · P&L summary                │
├────────────────────────────────────────────────────────────────────────────┤
│                    ┌──────────────────────────────────────┐                │
│                    │  Cards (Master Registry)             │                │
│                    │  what you own, qty, condition, loc   │                │
│                    └───────────────┬──────────────────────┘                │
│   ┌────────────────────┐           │ joins on              ┌──────────────┐│
│   │ Purchases (Ledger) │◄──────────┤ api_card_id+variant   │ Prices (cache)││
│   │  individual + bulk │           │                       │  current value││
│   └─────────┬──────────┘           │                       └──────┬───────┘│
│             │ allocates to         │                              │ appends │
│   ┌─────────▼──────────┐  ┌────────▼───────────┐   ┌──────────────▼───────┐│
│   │ BulkAllocation     │  │ CardCatalog (API)  │   │ PriceSnapshots (hist)││
│   │  cost spreading    │  │  id lookup cache   │   │  append-only history ││
│   └─────────┬──────────┘  └────────▲───────────┘   └──────────────────────┘│
│             │                      │ fed by                │               │
│   ┌─────────▼──────────┐  ┌────────┴───────────┐           │               │
│   │ Sets (reference)   │  │ RateLog (API usage)│◄──────────┘               │
│   │ set_id ↔ set_code  │  │ quota tracking     │                           │
│   └────────────────────┘  └────────────────────┘                           │
│                          Config (settings)                                 │
└────────────────────────────────────────────────────────────────────────────┘
```

| # | Tab | Role | Written by | Updated by |
| --- | --- | --- | --- | --- |
| 1 | `Cards` | Master registry of everything owned | You / import | You |
| 2 | `Purchases` | Every acquisition event (individual + bulk) | You | You |
| 3 | `BulkAllocation` | How bulk totals are spread over cards | Formulas / you | Formulas |
| 4 | `PriceSnapshots` | Append-only price history (one row per card per snapshot) | Automation | Automation |
| 5 | `Prices` | Current price cache (one row per card+variant) | Automation | Automation |
| 6 | `CardCatalog` | API card reference cache (id → metadata) | Automation | Automation |
| 7 | `Sets` | Set reference (from `/sets`) | Automation | Automation |
| 8 | `RateLog` | Every API call + remaining quota | Automation | Automation |
| 9 | `Config` | Settings: currency, price source, budgets, statuses | You | You |
| 10 | `Dashboard` | KPIs, charts, insights (formula-driven) | Formulas | Formulas |

---

## 5. Detailed Tab Schemas

> **Conventions used below:**
> - `key` columns are bold and are the join keys.
> - Columns marked `[API]` are filled by the API automation.
> - Columns marked `[auto]` are formulas.
> - `currency` is ISO (EUR for CardMarket, USD for TCGPlayer); we display primary currency from `Config`.

### 5.1 `Cards` — Master Collection Registry

One row per **card identity + condition**. Multiple copies of the same identity/condition share a row via `qty`.

| Column | Type | Description |
| --- | --- | --- |
| **card_id** | text | Internal stable key: `api_card_id` + `|` + `variant` + `|` + `condition` + `|` + `language` |
| **api_card_id** | text `[API]` | PokeWallet card ID (`pk_...` or bare hash) — the price/identity join key |
| variant | text `[API]` | `sub_type_name` (TCG) or `variant_type` (CM) — *which print of the card* |
| language | text | `en`, `de`, `jap`, ... |
| condition | text | NM / LP / MP / HP / D (affects resale value, not API price) |
| qty | number | How many physical copies of this identity/condition |
| set_id | text `[API]` | Numeric group id from API |
| set_code | text `[API]` | e.g. `FLF`, `SV2a` |
| set_name | text `[API]` | e.g. "XY - Flashfire" |
| card_number | text `[API]` | e.g. `107/106` |
| name | text `[API]` | Display name |
| rarity | text `[API]` | e.g. `Secret Rare` |
| card_type | text `[API]` | Pokemon / Trainer / Energy |
| stage / hp / attacks | text `[API]` | Optional enrichment |
| storage_location | text | Binder/box/shelf label |
| acquired_via | ref | Purchase id(s) from `Purchases` (comma list) |
| cost_per_copy | number `[auto]` | Total allocated cost ÷ qty (from `Purchases`/`BulkAllocation`) |
| notes | text | Free text (signed, graded, misprint, ...) |
| date_added | date | When the row was created |
| status | text | `owned` / `sold` / `wishlist` / `traded` |

**Why key on `api_card_id + variant + condition + language`?**
- Two copies of the same card in different conditions have different resale values → separate rows.
- Holo vs Reverse Holo vs 1st Edition have **different API prices** → must be distinct.
- The API price lookup needs `api_card_id` + `variant` only; condition/language are *your* dimensions layered on top.

### 5.2 `Purchases` — Acquisition Ledger

One row per **purchase event**. Individual card buys are simple rows; bulk lots have `is_bulk = TRUE` and reference a `BulkAllocation`.

| Column | Type | Description |
| --- | --- | --- |
| **purchase_id** | text | `P-0001`, `P-0002`, ... (your key) |
| date | date | Purchase date |
| source | text | Marketplace / shop / person (e.g. "FINN.no", "Cardmarket", "Cardmarket singles", "Local shop") |
| description | text | e.g. "79 reverse holo lot", "Charizard VMAX single" |
| **is_bulk** | boolean | TRUE if one price covers multiple cards |
| total_paid | number | Total cost incl. shipping/fees |
| currency | text | `EUR`, `NOK`, `USD`, ... |
| shipping_fees | number | Portion of `total_paid` that is shipping |
| tax_fees | number | Portion that is tax/fees |
| **paid_for_cards** | number `[auto]` | `total_paid − shipping_fees − tax_fees` → the amount to allocate to cards |
| allocation_method | text | `none` / `equal` / `fmv_weighted` / `bulk_rate` / `manual` / `lot_only` (see §6) |
| card_count | number | Number of cards in the purchase |
| invoice_ref | text | Receipt/invoice number or URL |
| notes | text | Free text |

### 5.3 `BulkAllocation` — Bulk Purchase Cost Spreading

One row per **card line within a bulk purchase**. This is where "how much of the 300 kr goes to this Charizard?" is answered.

| Column | Type | Description |
| --- | --- | --- |
| **purchase_id** | ref | → `Purchases` |
| **card_id** | ref | → `Cards` |
| line_qty | number | How many copies of this card in this purchase |
| allocation_method | text | Method used for *this line* |
| fmv_at_purchase | number | Fair market value of one copy at purchase date (from API or estimate) |
| alloc_factor | number `[auto]` | Weight this card gets (method-dependent) |
| alloc_price_per_copy | number `[auto]` | Final allocated cost per copy |
| alloc_total | number `[auto]` | `alloc_price_per_copy × line_qty` |
| notes | text | e.g. "spike card", "bulk filler" |

**Consistency rule:** `Σ alloc_total (across lines of a purchase) = paid_for_cards` (within rounding tolerance). The spreadsheet should flag any purchase where this doesn't balance (error-checking per user's rules — no silent "successfully" claims).

### 5.4 `PriceSnapshots` — Price History

Append-only. One row per **card × variant × snapshot run**.

| Column | Type | Description |
| --- | --- | --- |
| **snapshot_id** | text | `S-2026-08-20-0001` (auto) |
| **snapshot_date** | date | The date the run happened |
| **api_card_id** | text | → `Cards` / `CardCatalog` |
| variant | text | TCG `sub_type_name` / CM `variant_type` |
| tcg_market | number | TCGPlayer `market_price` |
| tcg_low / tcg_mid / tcg_high | number | TCGPlayer low/mid/high |
| cm_trend | number | CardMarket `trend` |
| cm_avg | number | CardMarket `avg` |
| cm_avg7 | number | CardMarket 7-day average |
| cm_avg30 | number | CardMarket 30-day average |
| currency | text | EUR (CM) / USD (TCG) |
| source | text | `search` / `card` / `prices-set` |
| run_id | text | Batch id of the snapshot run (for partial runs) |

**Growth:** A 500-card collection × weekly snapshots = 26k rows/year. Google Sheets handles this fine. Long-term: archive old years to a separate tab.

### 5.5 `Prices` — Current Prices Cache

One row per **card + variant** — the "latest known price" for instant lookups. Rebuilt or upserted on each price run.

| Column | Type | Description |
| --- | --- | --- |
| **api_card_id** | text | → key |
| variant | text | |
| name | text `[API]` | |
| tcg_market | number | Latest TCGPlayer market |
| tcg_low / tcg_mid / tcg_high | number | |
| cm_trend | number | Latest CardMarket trend |
| cm_avg7 / cm_avg30 | number | Built-in trend data |
| primary_price | number `[auto]` | The one we compare against (see `Config.price_source`) |
| primary_currency | text `[auto]` | |
| last_updated | datetime | When this row was refreshed |
| price_age_days | number `[auto]` | `TODAY() − last_updated` — flags stale prices |

### 5.6 `Sets` — Set Reference

Cached from `GET /sets`.

| Column | Type | Description |
| --- | --- | --- |
| **set_id** | text | Numeric group id |
| set_code | text | May be null for promo sets |
| name | text | |
| card_count | number | |
| language | text | `eng`, `jap`, `ger`, ... |
| release_date | text | |
| refresh_date | date | Last time this was synced |

### 5.7 `CardCatalog` — API Card Reference Cache

One row per **unique API card** we've ever resolved. This is our offline lookup table so we don't re-query the API for already-known cards.

| Column | Type | Description |
| --- | --- | --- |
| **api_card_id** | text | PokeWallet id |
| name / clean_name | text | |
| set_id / set_code / set_name | text | |
| card_number | text | |
| rarity / card_type / hp / stage | text | |
| languages | text | comma list of available languages |
| tcgplayer_url | text | |
| cardmarket_url | text | |
| first_seen | date | |
| last_seen | date | |

### 5.8 `RateLog` — API Usage Tracker

One row per API call. Non-negotiable for staying under the free limits.

| Column | Type | Description |
| --- | --- | --- |
| **timestamp** | datetime | UTC |
| endpoint | text | e.g. `/search`, `/cards/:id`, `/sets` |
| params | text | Query string (truncated) |
| http_status | number | 200 / 403 / 429 / ... |
| remaining_hour | number | From `X-RateLimit-Remaining-Hour` |
| remaining_day | number | From `X-RateLimit-Remaining-Day` |
| cache_hit | boolean | `X-Cache: HIT`? |
| notes | text | Purpose of the call |

**Purpose:** a formula in `Dashboard` shows "API left today: X · left this hour: Y", and automation can **abort** if `remaining_hour < batch_size`.

### 5.9 `Config` — Settings

| Key | Value | Description |
| --- | --- | --- |
| `price_source` | `cardmarket` | Primary price source (`cardmarket`/`tcgplayer`) |
| `primary_currency` | `EUR` | Display currency (NOK possible with conversion) |
| `display_currency_rate` | `1` | Manual FX rate if displaying in NOK |
| `snapshot_frequency` | `weekly` | `daily` / `weekly` / `monthly` |
| `price_refresh_batch` | `95` | Max API calls per run (leaves headroom) |
| `bulk_rate_common` | `0.02` | EUR per bulk common (Method C) |
| `api_base_url` | `https://api.pokewallet.io` | |
| `api_key_env` | `API_KEY_POKEWALLET` | Env var name — **never store the key in the sheet** |
| `last_price_run` | date | Bookkeeping |

---

## 6. Bulk Purchases — Deep Dive

This is the trickiest part of the design. A bulk purchase is: *one total price, many cards*. The question "how much did each card cost me?" has **no objectively correct answer** — it depends on what you're trying to measure. Here are the ways to think about it, and their consequences.

### 6.1 Why allocation matters

The allocation determines:
1. **Per-card cost basis** → per-card profit/loss.
2. **Collection-level P&L accuracy** → if you later sell individual cards, the "profit" number is only meaningful if the cost basis was sensible.
3. **Decision-making** → "should I sell this Charizard?" depends on its true cost basis.

**The key insight:** you cannot know a single card's *real* cost from a bulk price — you choose a *model* of cost. Different models answer different questions (see below).

### 6.2 Method A: Equal split

> `alloc_price_per_copy = paid_for_cards / total_cards`

**Example:** 79 reverse holos for 300 kr → 300 / 79 ≈ **3.80 kr per card**.

| Pros | Cons |
| --- | --- |
| Trivial to compute, zero API calls | Massively distorts P&L: a 0.50 kr bulk card shows "loss", a 200 kr hit shows "profit" of 196 kr |
| Great when all cards are near-equal value | Useless for mixed-value lots |

**Best for:** bulk lots where cards are genuinely similar in value, or when you only care about the *collection total* (equal split preserves the total exactly). **Worst for:** mixed lots with a few hits.

### 6.3 Method B: Fair-market-weight allocation

> `alloc_price_per_copy_i = paid_for_cards × (fmv_i / Σ fmv)`

Each card's cost is proportional to its **fair market value at purchase time** (looked up via API, or estimated).

**Example:** Lot of 5 cards, paid 500 kr. FMVs at purchase: A=300, B=100, C=50, D=40, E=10 (sum 500).
- A → 500 × (300/500) = **300 kr**
- B → **100 kr**, C → **50 kr**, D → **40 kr**, E → **10 kr**

| Pros | Cons |
| --- | --- |
| Most economically sensible: you "bought value" | Needs FMV at purchase time (API calls or estimates) |
| Per-card P&L is meaningful | FMV changes over time — the allocation is a *time capsule* of purchase-day values |
| The hit cards carry the cost; bulk cards stay cheap | More complex to build |

**Best for:** mixed lots where some cards are worth a lot more than others — the typical "binder of cards" purchase. **This is the default recommended method** for mixed-value lots.

> **Why "when they change in price differently, what do I attribute to what?"** — this is precisely why we allocate by FMV *at purchase time*. Future price changes are *not* attributed at purchase; they're captured later by comparing **current value** (from `PriceSnapshots`) against the **fixed cost basis** (from allocation). So a card that spikes after purchase shows a large gain *on that specific card*, exactly as you'd expect. The allocation method only affects the baseline, not the future movements.

### 6.4 Method C: Bulk-rate + residual method

> 1. Every bulk/common card gets a fixed "bulk rate" (e.g. `Config.bulk_rate_common` = 0.02 € or ~0.20 kr).
> 2. The remainder (`paid_for_cards − Σ bulk_rate`) is allocated to the *hits* (cards above bulk value), split by FMV weighting (Method B among hits only).

**Example:** "79 reverse holos" for 300 kr. Suppose 75 cards are bulk (0.20 kr each = 15 kr) and 4 are hits.
- Remainder = 300 − 15 = **285 kr** to the 4 hits, weighted by their FMV.

| Pros | Cons |
| --- | --- |
| Very realistic: bulk is bulk, hits carry the price | Requires a threshold for "what counts as a hit" |
| Matches how collectors actually reason ("I paid for the chance of hits") | Slightly more setup |

**Best for:** **sealed products and packs** (see §6.8), large bulk lots, and "79 reverse holo" style purchases where most cards are filler.

### 6.5 Method D: Manual / known prices

> You *know* the price of some cards (they had price tags, you haggled, or you looked them up at purchase). Assign those directly. The remainder of `paid_for_cards` then goes to the rest (via Method B or C).

**Best for:** purchases where a few cards have known prices and the rest is filler. Also the natural method for **individual card purchases** (cost basis = the price you actually paid).

### 6.6 Method E: Lot-level tracking (no per-card split)

> Don't split at all. The lot stays one entity with one cost; cards reference the lot but have `cost_per_copy = null`.

| Pros | Cons |
| --- | --- |
| Zero effort, no assumptions | No per-card P&L possible |
| Honest: "I don't know" | Can't answer "should I sell this card?" |

**Best for:** very cheap bulk you'll never sell individually, or as a *staging* state before you later allocate (you can upgrade a lot from Method E to B/C at any time — since allocation is a separate table, this is non-destructive).

### 6.7 Recommendation & worked example

| Purchase type | Recommended method |
| --- | --- |
| Single card | D (actual paid price) |
| Small lot (2–10 cards) | B (FMV-weighted) |
| Large bulk lot with hits | C (bulk-rate + residual) |
| All-similar bulk | A (equal) or E (lot-only) |
| Packs / boxes / sealed | C (see §6.8) |

**Worked example (Method C) — "79 reverse holo" lot, 300 kr, 4 hits:**

```
paid_for_cards = 300 kr
Bulk: 75 × 0.20 kr = 15 kr
Remainder to hits = 285 kr

Hits (FMV at purchase):
  Charizard VMAX    FMV 200 kr → 200/285 × 285 = 200.00 kr
  Pikachu V         FMV  55 kr →  55/285 × 285 =  55.00 kr
  Umbreon V         FMV  25 kr →  25/285 × 285 =  25.00 kr
  Gengar V          FMV   5 kr →   5/285 × 285 =   5.00 kr

Check: 200 + 55 + 25 + 5 = 285 ✓  (matches remainder)
Total: 15 + 285 = 300 ✓         (matches paid_for_cards)
```

### 6.8 Packs & sealed products

Opening a pack is the extreme version of bulk: 10 cards, one pack price, and **random pulls**.

**Recommended model (Method C):**
1. Log the pack as a `Purchases` row (`is_bulk = TRUE`, description "3× SV2a booster").
2. Record the **pulls** in `BulkAllocation` as they happen.
3. Allocate:
   - Hit cards → their FMV at pull time.
   - Bulk → bulk rate.
   - **Shortfall** (`paid − Σ allocations`) → keep it *unallocated* (record as "opening cost / entertainment" in the purchase notes) OR spread it over hits. **Recommendation:** keep it unallocated — it's honest (you didn't buy cards, you bought *chance*) and it prevents fake per-card P&L.

This also gracefully handles the user's actual FINN.no scenario: "Solgt 300 kr" (sold for 300 kr) entries can be `status = sold` in `Cards`, and the *sale* price is recorded separately (future enhancement: a `Sales` tab).

---

## 7. Price Tracking Over Time

Two complementary layers:

### Layer 1 — CardMarket's built-in trends (free)
Every `/search` / `/cards/:id` response includes `avg7`, `avg30`, `trend`. So even a *single* snapshot tells you "this card is +12% over 7 days / −4% over 30 days". This covers short/medium-term movement with **zero historical storage**.

### Layer 2 — Our own snapshot history (`PriceSnapshots`)
Since `/cards/:id/price-history` is Pro-only, we **build our own history**:
- On each run, write one row per card with today's prices → append-only.
- Over time this becomes *your* price chart, and `Dashboard` can compute % change since last snapshot, 30-day change, 90-day change, etc. from the stored series.

**Snapshot cadence recommendation:**
- **Daily:** the top-value cards (or a watchlist) — cheap, catches fast movers.
- **Weekly:** the full collection (matches CardMarket's `avg7` cycle).

### Which price to track?
- `Config.price_source` defaults to **CardMarket (`trend`)** — you're in Europe/Norway; CardMarket is the EU marketplace and prices are in EUR (your purchase currency context is NOK, so display-rate conversion in `Config`).
- TCGPlayer `market_price` stored alongside as a reference for US-market comparisons.

### Condition adjustments
The API price is for a **near-mint card**. Your played cards are worth less. Recommendation: a simple multiplier per condition stored in `Config` (e.g. NM 1.00 / LP 0.85 / MP 0.65 / HP 0.45 / D 0.25), applied on the Dashboard, *not* stored — so you can tune it without touching history.

---

## 8. Rate Limit Budget & Strategy

**Budget:** 100/hour, 1000/day. Verified that even cached hits count.

### Cost per operation (free plan)

| Operation | API calls |
| --- | --- |
| Add 1 card (search + detail) | 1–2 |
| Refresh price of 1 card | 1 |
| Refresh prices of whole collection (N unique cards) | **N** |
| Sync `/sets` | 1 |
| Build card catalog for a set | 1–2 per set (paginated) |

### The numbers that matter

| Collection size (unique cards) | Full price refresh cost | Time needed at 100/hr |
| --- | --- | --- |
| 50 | 50 | 30 min |
| 100 | 100 | 1 h |
| 300 | 300 | 3 h |
| 500 | 500 | 5 h |
| 1000 | 1000 | 10 h (uses whole daily budget) |

### Mitigation strategies (free plan)

1. **Staggered refresh by tier:**
   - **Tier 1 (top ~20 by value):** daily.
   - **Tier 2 (rest of the collection):** weekly, in batches of ~95.
2. **Leverage `/sets/:setCode` for catalog building** (not prices) — a whole set's card list (with IDs) costs just 1–2 calls, letting you resolve scanner imports cheaply.
3. **Reuse cached data:** `/search` results are cached 15 min, `/cards/:id` 60 min, `/sets` 120 min. If a card was refreshed < 60 min ago, skip it.
4. **RateLog guard:** automation reads `remaining_hour`/`remaining_day` before each batch and aborts with a clear message if the batch won't fit (no silent partial runs).
5. **Batch = 95 max** per run (leave 5/hour headroom for manual searches).

### The Pro option (worth discussing)

| Plan | Cost | Unlocks |
| --- | --- | --- |
| Free | €0 | 100/hr, 1000/day, per-card price calls |
| Pro | €20/month | 5000/hr, 50000/day, **`/prices/:setCode`** (whole set in 1 call!), `/price-history`, `/sets/statistics`, `/analytics/top-cards` |

With Pro, refreshing a 500-card collection across ~10 sets becomes **~10 API calls** instead of 500 — a 50× reduction. If the collection grows beyond ~300 unique cards, Pro is arguably the sane choice, and the **7-day free trial** lets us test the whole pipeline before committing.

**Recommendation:** design the spreadsheet so price fetching is *source-agnostic* (a `source` column in `PriceSnapshots`), so upgrading to Pro later is just a config change (`source = prices-set`), not a redesign.

---

## 9. Adding Cards — Workflows

### 9.1 Individual card entry

1. You type the card name (or scan a code) → automation calls `/search?q=<name>` (1 call).
2. Pick the exact result (set + number + variant). The automation stores the card in `CardCatalog` + `Cards` (with your condition/qty/location).
3. Price is captured into `Prices` from the same response (no extra call).

**To make this convenient:** the import form can accept:
- Free text name ("charizard ex")
- Set code + number ("FLF 107")
- Set id + number ("1464 107" — precise)
- CardMarket/TCGPlayer product URL (parsed for the ID)

### 9.2 Scanner app exports

Scanner apps (Collectr, TCGplayer app, DragonShield, Cardmarket app, etc.) typically export CSV/XLSX with columns like: *Set / Collector Number / Name / Count / Condition / Language / (sometimes) Price Paid*.

**Design implications (kept in mind, implemented in the import pipeline):**
- The import maps their columns → our `Cards` schema.
- **Resolution strategy (cheap on rate limits):**
  1. Group the export by `set_code` (or set name).
  2. For each set: call `/sets/:setCode` once (1–2 calls, limit 200/page) to get the **set's full card list with `api_card_id`s** → build a local map `card_number → api_card_id`.
  3. Match each export row by number (+ name sanity check) → `api_card_id`.
  4. Unmatched rows → `Unresolved` review list (never dropped silently).
- Because we resolve *per set* instead of *per card*, importing a 79-card export costs **~2–4 calls**, not 79.

### 9.3 Import pipeline design

```
Scanner CSV/XLSX
      │
      ▼
┌─────────────────┐    ┌──────────────────┐    ┌───────────────┐
│ Normalize       │───►│ Resolve via API  │───►│ Stage & review│──► Cards
│ (column mapping,│    │ (sets→id map,    │    │ (unresolved   │
│  trim, dedupe)  │    │  per-card check) │    │  list shown)  │
└─────────────────┘    └──────────────────┘    └───────────────┘
                              │
                              ▼
                         RateLog (audit)
```

---

## 10. Google Sheets Implementation Notes

- **Tabs are created via the Sheets MCP** (create_sheet), headers written once, then data flows via update_cells / batch_update_cells.
- **Named ranges** for key columns (e.g. `Cards_id`, `Prices_api_card_id`) make formulas readable.
- **Data validation** dropdowns: `condition` (NM/LP/MP/HP/D), `status` (owned/sold/traded/wishlist), `allocation_method`, `language`.
- **Conditional formatting:** flag `price_age_days > 14` (stale), flag bulk purchases where `Σ alloc ≠ paid_for_cards`, flag negative P&L.
- **Formulas** (see Appendix) for cost basis, current value, P&L, totals.
- **Automation:** Google Apps Script (bound to the spreadsheet) can run the API refresh on a schedule; it reads the key from **Script Properties / env**, never from a cell. The MCP handles the interactive steps; Apps Script handles the scheduled/background steps.
- **Never store the API key in the sheet.** It stays in the environment (`API_KEY_POKEWALLET`).

---

## 11. Dashboards & Views

### Dashboard (main view)
- Total cards owned, total unique cards, sets owned
- **Total paid** (sum of cost basis), **total current value**, **total unrealized P&L** (±, colored)
- Top 10 most valuable cards
- Top 10 gainers / losers since last snapshot (from `PriceSnapshots`)
- Set completion % (owned cards / set card_count, from `Sets`)
- API quota gauge (from `RateLog`)
- Stale-price alert count

### Future views (easy with pivot tables / QUERY)
- By set, by rarity, by type, by era (vintage / modern)
- By storage location (inventory audit)
- Price history chart per card (line chart from `PriceSnapshots`)
- Sold/traded history with realized P&L (needs a future `Sales` tab)

---

## 12. Implementation Roadmap

| Phase | What | Deliverable |
| --- | --- | --- |
| **1. Foundation** | Create all tabs, headers, `Config`, `Sets` sync, `RateLog` | Empty working skeleton + set reference |
| **2. Card entry (manual)** | Search → add card flow, `CardCatalog` + `Cards` population | First cards added |
| **3. Prices** | Price fetch + `Prices` cache + first `PriceSnapshots` run | Current values visible |
| **4. Purchases + allocation** | `Purchases`/`BulkAllocation` with the methods above + balancing check | Cost basis per card |
| **5. Dashboard** | KPIs, P&L, charts, quota gauge | Full overview |
| **6. Scanner imports** | CSV/XLSX import pipeline (per-set resolution) | Bulk add workflow |
| **7. Automation** | Apps Script scheduled price refresh, quota guards | Hands-off weekly updates |
| **8. Future** | `Sales` tab (realized P&L), condition multipliers, Pro upgrade path, views | Extended analysis |

---

## 13. Open Questions & Decisions Needed

1. **Primary price source:** CardMarket (EUR) recommended for Norway/EU. Confirm.
2. **Display currency:** EUR, or NOK via `Config.display_currency_rate`? (Purchases may be in NOK — FINN.no, Cardmarket EUR.)
3. **Snapshot cadence:** weekly for all + daily for top-20 acceptable?
4. **Pro upgrade:** want to try the 7-day trial now (unlocks `/prices/:setCode` + price-history), or stay free initially?
5. **Condition multipliers:** use the suggested NM/LP/MP/HP/D factors, or ignore condition for now?
6. **Scanner app in use:** which app(s) will you export from? (Affects column-mapping table.)
7. **Sold cards:** add a `Sales` tab now or later?

---

## Appendix: Key Formulas

Assume `Config!B2` = `price_source`, `Config!B3` = `primary_currency`.

**Primary price lookup** (in `Prices`):
```gs
=IF(Config!B2="cardmarket", cm_trend, tcg_market)
```

**Cost basis per copy** (in `Cards`, from `BulkAllocation`):
```gs
=IFERROR(SUMIFS(BulkAllocation!alloc_total, BulkAllocation!card_id, A2) / qty, "")
```

**Current value** (in `Cards`):
```gs
= qty * IFERROR(VLOOKUP(api_card_id & "|" & variant, {Prices!api_card_id & "|" & Prices!variant, Prices!primary_price}, 2, 0), 0)
```

**Unrealized P&L**:
```gs
= current_value - qty * cost_per_copy
```

**% change since last snapshot** (on Dashboard, per card):
```gs
= (latest.cm_trend - previous.cm_trend) / previous.cm_trend
```
(implemented via `INDEX(QUERY(PriceSnapshots...))` sorted by date desc)

**Bulk allocation balance check** (per purchase, flag if not ~0):
```gs
= IF(ABS(SUMIF(BulkAllocation!purchase_id, A2, BulkAllocation!alloc_total) - Purchases!paid_for_cards) > 0.01,
    "UNBALANCED", "OK")
```

**API quota left (from `RateLog`):**
```gs
= MIN(IFERROR(MIN(RateLog!remaining_hour), Config!B_budget_hour),
      Config!B_budget_hour)
```

---

*Plan complete — ready for Phase 1 implementation once the Google Sheets ID is confirmed.*
