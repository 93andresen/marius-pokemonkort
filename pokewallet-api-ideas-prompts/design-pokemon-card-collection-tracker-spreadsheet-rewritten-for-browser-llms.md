# Request: Design a Pokémon Card Collection Tracker Spreadsheet

I want to build a **Pokémon Card Collection Tracker** in Google Sheets and I need a comprehensive, well-thought-through **design plan** before anything is actually built.

## Your role in this conversation (important — please read)

You are being asked to **produce a written plan only**. In this chat you do **not** have access to tools, file reading, code execution, the API, or the spreadsheet — and you don't need any of that to answer. **Do not try to run, test, or "verify" anything.** Base your plan purely on the information provided below and your own knowledge of Google Sheets, data modeling, spreadsheets, and the Pokémon TCG.

## Context: who will use this plan

The plan you produce will be handed to an **implementation agent** that *does* have these capabilities:

- A **Google Sheets MCP server** — can read/write tabs, cells, and formulas in a real spreadsheet, so almost anything is possible there.
- **Code execution** — Python scripts to call APIs, parse data, and build import pipelines.
- A **PokeWallet API key** stored in the environment as a persistent env var named `API_KEY_POKEWALLET`, which the agent can use to test endpoints live.

So: design for that agent to implement. You may reference concrete API endpoints, spreadsheet formulas, tab schemas, and workflows, and you may mark things like *"implementing agent should verify this live with the key"* where you're unsure about API behavior. But keep in mind that **you yourself** won't be doing any of the implementation.

## The data source: PokeWallet API

Price data comes from the **PokeWallet API** (`https://api.pokewallet.io`), a Pokémon TCG database with real-time TCGPlayer & CardMarket pricing. The implementing agent has the full docs in a local file (`docs/pokewallet_io_api_docs.md`), but here are the essentials you need for planning:

- **Auth:** `X-API-Key: <API_KEY_POKEWALLET>` header.
- **Rate limits (free plan):** **100 requests/hour, 1000 requests/day.** Plan around this budget — it's a first-class constraint.
- **Free-plan endpoints:**
  - `GET /search?q=...` — find cards by name or precisely by `set_id + card_number`; returns full TCGPlayer + CardMarket pricing (cached 15 min).
  - `GET /cards/:id` — full card detail + pricing (cached 60 min).
  - `GET /sets` — list all sets (~150).
  - `GET /sets/:setCode` — cards in a set (metadata only, **no prices**).
  - `GET /images/:id` — card image.
- **Pro-only / blocked on the free plan (design around NOT having these):**
  - `GET /prices/:setCode` — all prices for an entire set in one call (would be the rate-limit holy grail, but blocked).
  - `GET /cards/:id/price-history` — official price history (blocked → history must be built from our own snapshots).
  - Set statistics, trending, completion-value endpoints (blocked).
- **Price payloads:**
  - TCGPlayer per variant: `low_price, mid_price, high_price, market_price, direct_low_price, updated_at`.
  - CardMarket per variant: `avg, low, avg1, avg7, avg30, trend, updated_at` — the `avg7`/`avg30`/`trend` fields give free "price change over time" data on every request.
- **Card ID formats:** `pk_<hash>` (TCG cards, also carry CardMarket data when available) and bare hex hashes (CardMarket-only cards, e.g. Japanese sets). `set_id + card_number` is the precise search key.
- **Note:** cached API responses still count against the rate limit — every call costs quota.

## What the tracker must do

Its main purposes:
- **Overview of all my cards.**
- **Price changes over time.**
- **Current prices.**

Plus everything else a serious Pokémon card collector wants. Requirements to design for:

- **Price paid for each card** — and specifically, resolve these hard cases:
  - **Bulk purchases:** how do you attribute cost when many cards are bought together (lots, binders, sealed deals)?
  - **Differential price changes:** when cards in a bulk lot appreciate/depreciate at different rates, how should cost basis be handled, and what gets credited to which card?
  - **Different ways of thinking about this, and the trade-offs of each.**
- **Bulk allocation must be explicit and auditable** — it should always be answerable *why* a card has the cost basis it does.
- **Price history:** how to track prices over time given that official history endpoints are blocked on the free plan.
- **Current price tracking** within the rate-limit budget.
- **Individual card entry:** adding single cards conveniently (typing a card name, auto-fetching data from the API).
- **Scanner app exports:** I use scanners for many cards and will export lists from scanner apps (bulk CSV/Excel-style imports). The design must tolerate messy external data and dedupe/import it cleanly. Cover this later if needed, but keep it in mind when designing the system.
- **API rate-limit strategy** — a visible budget and workflow so 100/hr and 1000/day are never accidentally blown.

## Output

Produce a **complete markdown document** with a comprehensive, well-thought-through plan for creating this spreadsheet. Feel free to include different suggestions and options — I'm open to anything useful. Cover:

1. The optimal spreadsheet structure and **why** (tab-by-tab schema, key columns, relationships).
2. Bulk purchase cost-allocation methods (multiple approaches, trade-offs, a recommendation, and a worked example).
3. Price tracking over time and current-price caching strategy within rate limits.
4. Workflows for adding cards (individual entry + scanner exports).
5. Dashboards/views for the collector use cases.
6. Any formulas, conventions, or implementation notes useful for the implementing agent.
7. Open questions or decisions I need to make.

---

**Target spreadsheet (for the implementing agent):**

Google Sheets Link:
https://docs.google.com/spreadsheets/d/13TfMos8hP4zT3-Tf92F7ZE0hJ2r7cKJdEqvdj0gvtpM/edit?gid=0#gid=0

Google Sheets ID:
13TfMos8hP4zT3-Tf92F7ZE0hJ2r7cKJdEqvdj0gvtpM
