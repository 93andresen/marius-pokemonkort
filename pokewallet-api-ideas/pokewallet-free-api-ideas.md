# PokeWallet Free API — Everything You Can Do With It

> **Version:** 1.0 · **Date:** 2026-08-20
>
> **Base URL:** `https://api.pokewallet.io` · **Auth:** `X-API-Key` header · **Key env var:** `API_KEY_POKEWALLET`
>
> **Free plan limits:** 100 requests/hour · 1,000 requests/day
>
> **Companion docs:** [`docs/pokewallet_io_api-docs.md`](pokewallet_io_api-docs.md) (full API reference) · [`docs/pokemon-card-collection-tracker-plan.md`](pokemon-card-collection-tracker-plan.md) (spreadsheet design)

---

## Table of Contents

1. [What the Free Plan Actually Gives You](#1-what-the-free-plan-actually-gives-you)
2. [The Free API Toolbox — Endpoint by Endpoint](#2-the-free-api-toolbox--endpoint-by-endpoint)
3. [The Rate Limit Reality Check](#3-the-rate-limit-reality-check)
4. [Ideas for the Spreadsheet Tracker](#4-ideas-for-the-spreadsheet-tracker)
5. [Ideas That Work WITHOUT the Spreadsheet](#5-ideas-that-work-without-the-spreadsheet)
6. [Buying & Selling Intelligence](#6-buying--selling-intelligence)
7. [Discovery, Wishlists & Set Completion](#7-discovery-wishlists--set-completion)
8. [Automation & Scripts](#8-automation--scripts)
9. [Fun, Creative & Social Ideas](#9-fun-creative--social-ideas)
10. [Data Enrichment Ideas](#10-data-enrichment-ideas)
11. [Idea Matrix — Effort vs. Value vs. API Cost](#11-idea-matrix--effort-vs-value-vs-api-cost)
12. [The Pro Upgrade Question](#12-the-pro-upgrade-question)
13. [Quick-Start Recipes](#13-quick-start-recipes)

---

## 1. What the Free Plan Actually Gives You

The free plan is **not** a crippled demo. It gives you the full 50,000+ card database, real-time TCGPlayer **and** CardMarket pricing, card images, and set data. What it *withholds* is the **bulk/analytics endpoints** (whole-set price dumps, price history, trending, completion value).

| Capability | Free plan | Pro plan |
| --- | --- | --- |
| Search any card by name / set / number | ✅ | ✅ |
| Full card details (stats, attacks, text) | ✅ | ✅ |
| Current prices — TCGPlayer (USD) + CardMarket (EUR) | ✅ | ✅ |
| CardMarket built-in trends (`avg7`, `avg30`, `trend`) | ✅ | ✅ |
| Card images (EN + 5 localized languages) | ✅ | ✅ |
| All sets list + per-set card lists | ✅ | ✅ |
| Whole-set price dump in 1 call (`/prices/:setCode`) | ❌ | ✅ |
| Official 7/14/30/60/120-day price history | ❌ | ✅ |
| Set statistics, trending sets, completion value, top cards | ❌ | ✅ |
| Rate limits | 100/hr · 1,000/day | 5,000/hr · 50,000/day |

**The single most important insight:** on the free plan, **every price lookup costs 1 request** (via `/search` or `/cards/:id`). There is no "give me all prices for this set" shortcut. Everything below is designed around that constraint.

**The second most important insight:** every `/search` and `/cards/:id` response already contains CardMarket's `avg7`, `avg30`, and `trend` fields. That means **even a single request tells you how a card has moved over the last 7 and 30 days** — free trend data with zero history storage. This is the backbone of many ideas below.

---

## 2. The Free API Toolbox — Endpoint by Endpoint

### 2.1 `GET /search?q=...` — the workhorse (1 request per card)

The Swiss Army knife. One call returns: card identity (name, set, number, rarity, type, HP, stage, attacks, weakness, resistance, retreat cost), available image languages, **and full current pricing from both marketplaces**.

**Query formats it accepts:**
| You type | What it does | Example |
| --- | --- | --- |
| Card name | Fuzzy name search | `q=charizard ex` |
| Set code | All cards in a set | `q=SV2a` |
| Card number | Cards with that number | `q=148` |
| `set_id + card number` | **Precise lookup** — the killer feature | `q=24541 148` |

> **Why `set_id + card number` matters:** it's the *exact* card, no ambiguity, no picking from a list. This is what makes scanner-export resolution and precise lookups cheap and reliable. Every card in every response carries its `set_id` and `set_code`, so you can always build the precise key for later.

### 2.2 `GET /cards/:id` — full detail for one card (1 request per card)

Same data as `/search` but by stable card ID (`pk_...` for TCG cards, bare hex hash for CardMarket-only cards). Use it when you already know the ID (from a cache, a previous search, or a stored collection). Cached 60 minutes.

### 2.3 `GET /sets` — the whole set universe (1 request total!)

**All ~150 sets in one call**: name, `set_code`, `set_id`, `card_count`, `language`, `release_date`. This is the cheapest endpoint on the API and the foundation for set completion tracking, set browsing, and import resolution.

### 2.4 `GET /sets/:setCode` — a set's full card list (1–2 requests per set)

Paginated card list (up to 200/page) with **every card's `api_card_id`** and metadata. Prices arrays are empty here — this is a *catalog* endpoint, not a *pricing* endpoint. But it's the key to resolving scanner exports cheaply (see §4.4).

> **Disambiguation gotcha:** some set codes (e.g. `PR`) map to multiple sets. The API returns a disambiguation list; use the numeric `set_id` to be unambiguous. Always prefer `set_id` over `set_code` in your stored data.

### 2.5 `GET /images/:id` — card artwork (1 request per image)

Card images in `low` (~500px) or `high` (~1000px), plus **localized artwork in Italian, French, German, Spanish, Portuguese** (WebP). The `images.languages` array on any card tells you which languages exist. Images are cached for a year (`Cache-Control: immutable`) — so you can download once and never pay again.

### 2.6 `GET /health` and `GET /` — free, no auth

Health check and API info. Useful for monitoring scripts and uptime checks — they don't count against your key's quota (no auth needed).

### 2.7 What's blocked on free (and what you lose)

| Blocked endpoint | What you lose | Free-plan workaround |
| --- | --- | --- |
| `/prices/:setCode` | Whole-set prices in 1 call | Per-card lookups (N calls) |
| `/cards/:id/price-history` | Official price history | Build your own via snapshots + `avg7`/`avg30` |
| `/sets/:setCode/statistics` | Set avg/min/max prices | Compute from your own card lookups |
| `/sets/trending` | Hot sets | Track your own watchlist |
| `/sets/:setCode/completion-value` | Set completion cost | Sum per-card prices yourself |
| `/analytics/top-cards` | Market movers | Your own collection's movers |

---

## 3. The Rate Limit Reality Check

**Budget:** 100/hour, 1,000/day. **Verified:** even cached responses (`X-Cache: HIT`) count against the quota.

### Cost per operation

| Operation | API calls |
| --- | --- |
| Look up 1 card's price | 1 |
| Add 1 card to collection (search) | 1 |
| Refresh whole collection (N unique cards) | N |
| Sync all sets | 1 |
| Get a set's full card list | 1–2 |
| Download 1 card image | 1 (then cached forever) |

### What fits in a day

| Collection size (unique cards) | Full price refresh | Feasible daily? |
| --- | --- | --- |
| 50 | 50 calls | ✅ easily |
| 100 | 100 calls | ✅ (10% of daily) |
| 300 | 300 calls | ⚠️ yes, but eats 30% |
| 500 | 500 calls | ⚠️ half the daily budget |
| 1,000 | 1,000 calls | ❌ uses the entire day |

### The golden rules for staying under budget

1. **Never re-query what you already know.** Cache card IDs + metadata locally (spreadsheet `CardCatalog` tab, or a JSON/CSV file). Only prices go stale.
2. **Batch by set, not by card.** One `/sets/:setCode` call resolves *every* card in that set for imports.
3. **Stagger by value.** Top-20 cards daily, the rest weekly.
4. **Respect the hour.** Max ~95 calls per batch, leaving headroom for manual lookups.
5. **Read the headers.** Every response has `X-RateLimit-Remaining-Hour` and `X-RateLimit-Remaining-Day`. Log them, and abort batches that won't fit.

---

## 4. Ideas for the Spreadsheet Tracker

These build directly on the existing plan in [`docs/pokemon-card-collection-tracker-plan.md`](pokemon-card-collection-tracker-plan.md).

### 4.1 Auto-fill card metadata on entry

Type a card name (or `set_id + number`) → one `/search` call → auto-fill name, set, number, rarity, type, HP, stage, attacks, weakness, resistance, retreat cost, and both marketplaces' prices. **No more manual data entry, no more typos in card names.**

### 4.2 Live collection value

Every card row gets its current value from the `Prices` cache. Sum it → **total collection value** on the Dashboard. Refresh the cache on a schedule (see §8) and you always know what you're sitting on.

### 4.3 Price snapshots → your own price history

Since official price history is Pro-only, **build your own**: each refresh run appends one row per card to `PriceSnapshots`. After a few weeks you have real charts: "my Charizard went from 200 kr to 310 kr over 3 months." Combined with CardMarket's built-in `avg7`/`avg30`, you get both short-term and long-term movement.

### 4.4 Scanner export resolution (the big one)

You export lists from scanner apps. The export has set + number + name, but no API IDs. Instead of looking up each card individually (N calls), do this:

1. Group the export by set.
2. For each set: one `/sets/:setCode` call → build a local map `card_number → api_card_id`.
3. Match every export row by number (+ name sanity check).
4. Unresolved rows go to a review list — never silently dropped.

**A 79-card export costs ~2–4 API calls, not 79.** This is the single biggest rate-limit win available.

### 4.5 Duplicate & playset detection

With stable `api_card_id` + variant keys, the sheet can instantly flag: "You already own 3 of these — adding 2 more makes a playset of 5." Useful for bulk lots where the same card appears multiple times.

### 4.6 Bulk purchase allocation with real FMV

The plan's Method B/C (FMV-weighted allocation) needs **fair market value at purchase time**. The API provides it: look up each hit card once when you log the purchase, and the allocation writes itself. The "79 reverse holos for 300 kr" problem becomes: 75 bulk cards at bulk rate + 4 hits weighted by their real market value.

### 4.7 Set completion dashboard

`/sets` gives you every set's `card_count`. Compare against your owned cards per set → **completion % per set**, "missing 12 cards from SV2a", and a prioritized "cheapest missing cards" list (look up the missing ones' prices).

### 4.8 Condition-adjusted value

API prices are for near-mint. Store your card's condition (NM/LP/MP/HP/D) and apply a multiplier on the Dashboard (NM 1.0 / LP 0.85 / MP 0.65 / HP 0.45 / D 0.25). Your *realistic* collection value is then honest, and you can tune multipliers without touching history.

### 4.9 Card images in the sheet

`/images/:id?size=low` → paste into a `CardImage` column (or a linked image folder). A visual inventory is *enormously* more pleasant to browse than a text list, and images are cached forever after the first download.

### 4.10 Watchlist tab with auto-refresh

A dedicated `Watchlist` tab: cards you're eyeing (for buying or selling). Refresh just those (10–20 cards = 10–20 calls) daily. See price, `avg7`/`avg30` trend, and a "buy/sell signal" computed from the trend.

### 4.11 P&L per card, per set, per era

Cost basis (from purchases) vs. current value (from API) → unrealized P&L. Roll up by set, by era (vintage/modern), by rarity. "My vintage binder is up 40%, my modern is flat" — real portfolio thinking.

### 4.12 Trade value calculator

Two cards, two lookups, one answer: "Is my card worth more than yours?" The API gives both marketplaces, so you can compare in EUR (CardMarket) or USD (TCGPlayer) — and see the spread between them.

### 4.13 "What did I pay vs. what is it worth" audit

The classic collector's reality check. Sort by `current_value − cost_basis` to find your best and worst purchases. The API makes the "current value" side always fresh.

### 4.14 Language-aware collection

The API knows which localized prints exist (`images.languages`). If you collect German cards (or want to), the API can tell you whether a German print exists and fetch its artwork — useful for EU collectors where language matters for value.

---

## 5. Ideas That Work WITHOUT the Spreadsheet

The API is fully usable standalone. Here are ideas that need nothing but a script and the key.

### 5.1 CLI price checker

`pokeprice "charizard ex"` → prints name, set, number, TCGPlayer market, CardMarket trend, and 7/30-day change. The most useful 20-line script you'll write. Great for checking a card while browsing FINN.no or Cardmarket.

### 5.2 Bulk lot valuation tool

Paste a list of cards (from a marketplace listing, a binder photo, a friend's offer) → script looks each up → **total estimated value** + per-card breakdown. This is the "should I buy this lot for 2,000 kr?" answerer. With the per-set resolution trick, a 50-card lot costs ~2–5 calls.

### 5.3 Price alert bot

A script that checks a watchlist on a schedule and notifies you (email, Discord webhook, ntfy, Telegram) when:
- A card drops below your target buy price
- A card you own crosses your sell target
- A card's `avg7` change exceeds a threshold (momentum alert)

10 cards × 1 call each = 10 calls/day. Trivial within budget.

### 5.4 Pack EV (expected value) calculator

Before buying sealed product: look up the set's chase cards, sum their prices × pull odds (rough), compare to pack price. "Is this SV2a booster box worth it?" The API gives you the card prices; you supply the odds. Even a rough EV beats buying blind.

### 5.5 Card image downloader / wallpaper generator

Download high-res artwork for your favorite cards. The images are gorgeous and cached forever. Use them for: phone wallpapers, a rotating desktop background, a printed binder cover, a "collection wall" display, or a screensaver.

### 5.6 Set browser / card database explorer

A tiny web page or script: pick a set from `/sets` → browse its cards with images and prices. Better than scrolling Cardmarket's website, and it's *your* tool. Also great for pre-release research: "what's in the new set, and what's worth chasing?"

### 5.7 Trade helper

Two cards in, two cards out. Script prints both sides' values from both marketplaces and the difference. No more "is this fair?" guesswork at the trade table.

### 5.8 Gift idea generator

"Find me a cool card under 15 EUR" → search a few sets, filter by price, return a shortlist with images. Perfect for birthday gifts for a Pokémon-obsessed kid (or yourself).

### 5.9 Market spread watcher

TCGPlayer (USD) vs CardMarket (EUR) prices often diverge. A script that tracks the spread on your cards tells you **where to sell** (US market vs EU market) and **where to buy**. For a Norwegian collector, this is genuinely actionable: CardMarket is your market, but knowing a card is 30% cheaper on TCGPlayer is useful intel.

### 5.10 Collection value snapshot script

No spreadsheet needed: a JSON/CSV file of your card IDs + a script that refreshes prices and prints a summary. "412 cards, 3,240 EUR CardMarket trend, +2.1% this week." A poor man's portfolio tracker that takes 10 minutes to build.

### 5.11 Random card of the day

Pick a random set, pick a random card, print its art + stats + price. Fun for a daily ritual, a Discord bot, or a "card of the day" widget.

### 5.12 Card trivia / quiz generator

The API has attacks, HP, weakness, rarity, set, release date. Generate quiz questions: "Which card has 330 HP and a Fire Spin attack?" — a fun way to learn your collection, or a party game.

### 5.13 Deck-building helper

Search by type, HP, stage, attacks. "Show me all Fire-type Basics with 100+ HP" → the API's card metadata makes this possible. Not a full deckbuilder, but a solid card-finder for casual play.

### 5.14 Price history logger (self-hosted)

Even without the spreadsheet: a cron job that appends today's prices for your watchlist to a CSV/SQLite file. After 3 months you have your own price charts — the free-plan answer to the Pro-only price-history endpoint.

### 5.15 "Is this listing a scam?" checker

Found a suspiciously cheap Charizard on a marketplace? Look up its real market price and see the gap. The API gives you the truth in one call.

---

## 6. Buying & Selling Intelligence

### 6.1 Buy-side checklist

Before any purchase, run the card through the API:
- **Market price** (CardMarket trend for EU) — what it's actually worth
- **`avg7` / `avg30`** — is it rising or falling? Buying a falling card means catching a knife; buying a rising one means momentum.
- **TCGPlayer comparison** — is the EU price out of line with the US price?

### 6.2 Sell-side checklist

- Is `trend` above `avg30`? → momentum is up, good time to sell.
- Is `trend` below `avg7`? → recent dip, maybe wait.
- Which marketplace pays more for *this* card? (spread watcher, §5.9)

### 6.3 Bulk lot valuation before buying

The killer use case for a Norwegian collector buying lots on FINN.no: paste the lot's card list → get total value → compare to asking price. If the lot is 79 reverse holos, the per-set resolution trick makes this nearly free.

### 6.4 Sealed product EV

Before buying packs/boxes: the set's chase cards' prices tell you the EV ceiling. Combined with your own pull luck, you can decide whether packs are "worth it" or whether you should just buy singles.

### 6.5 Sell-through planning

For cards you plan to sell: track their price for 2–4 weeks (cheap, 1 call/day each), then sell into strength. The `avg7`/`avg30` data from a single call already gives you the trend — you don't even need the history.

---

## 7. Discovery, Wishlists & Set Completion

### 7.1 Set completion tracker (spreadsheet or standalone)

`/sets` (1 call) + your owned list → per-set completion %. The missing-cards list can then be priced (1 call per missing card, or per-set resolution).

### 7.2 Wishlist with live prices

Keep a wishlist of card IDs. Refresh prices on demand (or daily). See total wishlist cost, and get alerts when something drops into budget.

### 7.3 Pre-release research

New set announced → `/sets/:setCode` gives you the full card list with rarities → look up the chase cards' prices → know what to chase before the set even releases.

### 7.4 "Cheapest way to complete a set"

For a set you're close to completing: list the missing cards, price them, sort by cost. Complete the set in the most economical order. (The Pro `completion-value` endpoint does this in one call — but you can do it manually for a handful of missing cards.)

### 7.5 Set browsing for nostalgia

Browse the sets you collected as a kid. See the cards, the prices, the release dates. The API is a time machine for collectors.

---

## 8. Automation & Scripts

### 8.1 The daily price refresh

A scheduled script (cron / Task Scheduler / GitHub Actions) that:
1. Reads your card ID list (from the spreadsheet or a file).
2. Checks `X-RateLimit-Remaining-*` headers.
3. Refreshes prices in batches of ≤95.
4. Appends to `PriceSnapshots` / updates the `Prices` cache.
5. Logs everything to `RateLog`.

### 8.2 The alert bot

Watchlist + thresholds + notification channel. Runs every few hours, stays well under budget.

### 8.3 The import pipeline

Scanner CSV/XLSX → normalize → per-set resolution → staged review → merged into the collection. The most complex automation, but the one that saves the most manual work.

### 8.4 The rate-limit sentinel

A tiny script that hits `/health` (free, no auth) and reads the API root — plus a check of your logged headers — to warn you before you're about to blow the hourly budget. Cheap insurance.

### 8.5 The image cache warmer

Download all images for your collection once (cached forever). Then any future tool that needs images never touches the API again.

### 8.6 The report generator

Weekly email/summary: collection value, top movers, alerts triggered, API usage. Generated from your snapshot history + a few fresh lookups.

---

## 9. Fun, Creative & Social Ideas

- **Card of the day** bot (Discord/Telegram) — art + stats + price.
- **Collection value bragging rights** — "my binder is worth X" with a live number.
- **Card art screensaver / wallpaper rotator** — high-res art from `/images`.
- **Trivia night generator** — questions from real card data.
- **"What would my collection buy?"** — total value in packs, boxes, or a specific chase card.
- **Trade night helper** — print value cards for each card you bring.
- **A "price museum"** — log prices over time and look back at what cards cost in 2026.
- **Gift finder** — budget-limited card suggestions with images.
- **Collection showcase page** — a simple HTML page with your cards' images and prices, shareable with friends.
- **Pack-opening companion** — log your pulls, the API prices them instantly, and you see your pack's "value pulled" in real time.

---

## 10. Data Enrichment Ideas

The API isn't just prices — every card carries rich metadata you can use:

| Field | What you can do with it |
| --- | --- |
| `attacks`, `hp`, `stage`, `weakness`, `resistance`, `retreat_cost` | Deck-building, trivia, gameplay reference |
| `rarity` | Rarity distribution charts, "rarest card" stats |
| `card_type` | Type breakdowns (Fire/Water/etc.), type-based browsing |
| `set_name`, `release_date` | Era analysis (vintage vs modern), timeline views |
| `images.languages` | Language-aware collection, localized artwork |
| `tcgplayer.url`, `cardmarket.product_url` | Direct links to buy/sell the exact card |
| `set_id` + `card_number` | The precise lookup key — the backbone of everything |

---

## 11. Idea Matrix — Effort vs. Value vs. API Cost

| Idea | Effort | Value | API cost | Where |
| --- | --- | --- | --- | --- |
| CLI price checker | ★ | ★★★★ | 1/card | Standalone |
| Bulk lot valuation | ★★ | ★★★★★ | 2–5/lot | Standalone |
| Scanner import resolution | ★★★ | ★★★★★ | 2–4/export | Spreadsheet |
| Price snapshots (own history) | ★★ | ★★★★ | N/week | Both |
| Watchlist + alerts | ★★ | ★★★★ | 10–20/day | Both |
| Set completion tracking | ★★ | ★★★★ | 1 + missing | Both |
| Collection value dashboard | ★★ | ★★★★★ | N/refresh | Spreadsheet |
| Card images in collection | ★ | ★★★ | 1/card (once) | Both |
| Pack EV calculator | ★★ | ★★★ | 5–10/set | Standalone |
| Market spread watcher | ★★ | ★★★ | 2×N | Standalone |
| Trade value calculator | ★ | ★★★ | 2/trade | Both |
| P&L by set/era/rarity | ★★★ | ★★★★ | 0 (uses cache) | Spreadsheet |
| Card of the day bot | ★ | ★★ | 1–2/day | Standalone |
| Trivia generator | ★★ | ★★ | 1–2/session | Standalone |
| Gift finder | ★★ | ★★ | 5–10/search | Standalone |
| Deck-building helper | ★★★ | ★★ | varies | Standalone |
| Price history logger | ★★ | ★★★★ | N/day | Standalone |

**The sweet spot:** CLI price checker + bulk lot valuation + scanner import resolution + price snapshots. That's 80% of the value for 20% of the effort, and it all fits comfortably in the free budget.

---

## 12. The Pro Upgrade Question

| | Free | Pro (€20/month) |
| --- | --- | --- |
| Per-card price lookup | 1 call each | 1 call each |
| Whole-set prices | ❌ | ✅ **1 call per set** |
| Price history | Build your own | ✅ Official |
| Set statistics / trending / completion value | ❌ | ✅ |
| Rate limits | 100/hr · 1,000/day | 5,000/hr · 50,000/day |

**When Pro becomes worth it:** roughly when your collection exceeds ~300 unique cards *and* you want frequent full refreshes. At 500 cards, a full refresh is 500 calls (half your daily budget) on free — or ~10 calls with Pro's `/prices/:setCode`. That's a 50× reduction.

**The smart play:** design everything so the price source is a config value (`search`/`card` today, `prices-set` after upgrade). The **7-day free trial** lets you test the whole Pro pipeline before paying. Nothing in this document requires Pro — but the ideas scale up to it seamlessly.

---

## 13. Quick-Start Recipes

### Recipe 1: The 10-minute price checker (standalone)

```bash
# One-liner to check a card's price
curl -H "X-API-Key: $API_KEY_POKEWALLET" \
  "https://api.pokewallet.io/search?q=charizard+ex" | jq '.results[0] | {name: .card_info.name, set: .card_info.set_name, tcg_market: .tcgplayer.prices[0].market_price, cm_trend: .cardmarket.prices[0].trend}'
```

### Recipe 2: The lot valuation flow

1. Paste the lot's cards into a text file (one per line: `set_id number` or `set_code number`).
2. Script groups by set → 1 `/sets/:setCode` call per set → resolves all IDs.
3. Script looks up prices for the resolved IDs (or uses the search response directly).
4. Output: per-card value + total + "asking price vs. value" verdict.

### Recipe 3: The weekly snapshot flow (spreadsheet)

1. Monday: read all `api_card_id`s from `Cards`.
2. Batch of ≤95: `/cards/:id` each → write to `PriceSnapshots` + update `Prices`.
3. Repeat Tuesday–Friday if the collection is large.
4. Dashboard recomputes value, P&L, and movers automatically.

### Recipe 4: The alert flow

1. `Watchlist` file: `card_id, min_buy_price, max_sell_price`.
2. Every 6 hours: look up each card (1 call), compare, notify on threshold crossing.
3. 20 cards × 4 runs/day = 80 calls/day — fits the budget with room to spare.

---

*This document is a menu, not a mandate. Pick the ideas that match how you actually collect, and the rate-limit rules in §3 will keep you safe no matter which ones you build.*
