# PokeWallet API — Live-Verified Notes

> Companion to [`pokewallet_io_api-docs.md`](pokewallet_io_api-docs.md). Everything here was observed
> against the **live** API, not copied from the docs. When the docs and this file disagree, **this file
> wins** (the docs are behind the deployed build).
>
> **Verified:** 2026-10-02 · **Environment:** `API_KEY_POKEWALLET` set · **Client:** `curl` / Python.
> Raw captures backing these notes live in [`../data/pokewallet/raw/`](../data/pokewallet/raw/)
> (one `.json` + `.headers.txt` pair per call).

---

## 1. Deployment facts

| Item | Docs say | **Live (verified)** |
|---|---|---|
| API version | `1.1.0` | **`1.7.1`** |
| Base URL | `https://api.pokewallet.io` | same |
| Auth header | `X-API-Key` | same |

`GET /` and `GET /health` both return healthy on the free plan.

---

## 2. Rate limits (verified from response headers)

```
X-RateLimit-Limit-Day:      1000
X-RateLimit-Limit-Hour:     100
X-RateLimit-Remaining-Day:  <n>
X-RateLimit-Remaining-Hour: <n>
```

- **100 requests/hour**, **1000/day**, on the free plan.
- Responses served from cache (`X-Cache: HIT`) **still count** against the quota.
- Always read the remaining counters and never spend the last few — say, keep a floor of ~10/hour
  for interactive use.

Header sample (from `GET /search?q=pikachu&limit=1`):

```
HTTP/1.1 200 OK
Content-Type: application/json
Cache-Control: public, max-age=900
X-Cache: MISS
X-RateLimit-Limit-Day: 1000
X-RateLimit-Limit-Hour: 100
X-RateLimit-Remaining-Day: 1000
X-RateLimit-Remaining-Hour: 100
```

---

## 3. Endpoint availability on the free plan

**Accessible:** `/`, `/health`, `/search`, `/cards/:id`, `/sets`, `/sets/:setCode`, `/images/:id`.

**PRO-blocked** — every one of these returned `{"error":"Trial not activated", ...}`:

- `/prices/:setCode`
- `/cards/:id/price-history`
- `/sets/:setCode/statistics`
- `/sets/trending`
- `/sets/:setCode/completion-value`
- `/analytics/top-cards`

> **Implication:** no bulk prices and no server-side price history. Prices must be fetched **per card**
> and history must be **built by us** via scheduled snapshots. See `PROJECT-PLAN.md` §9.

---

## 4. Cache TTLs (from `Cache-Control`)

| Endpoint | `max-age` | TTL |
|---|---|---|
| `/search` | 900 | 15 min |
| `/cards/:id` | 3600 | 60 min |
| `/sets` | 7200 | 120 min |

---

## 5. Response shape — `GET /search?q=pikachu&limit=1`

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
        "set_code": "BA24",
        "set_id": "23520",
        "card_number": "004",
        "rarity": "Common",
        "card_type": "Basic Lightning Energy",
        "product_type": "card",
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

### 5.1 Discrepancies vs. the docs

1. **`product_type`** exists inside `card_info` — not documented (value seen: `"card"`).
2. **`set_code`** live value is `"BA24"`, docs example was `"BA2024"` — prefer `set_id` and never
   key logic on `set_code`.
3. Version is `1.7.1` (docs `1.1.0`).

### 5.2 Card id formats

- `pk_<hex>` → TCGPlayer-backed card.
- bare `<hex>` → CardMarket-only card (no TCGPlayer data).

### 5.3 Price fields

| Source | Fields |
|---|---|
| TCGPlayer | `low_price, mid_price, high_price, market_price, direct_low_price, updated_at, sub_type_name` |
| CardMarket | `avg, low, avg1, avg7, avg30, trend, updated_at, variant_type` |

`cardmarket` (and sometimes `tcgplayer`) can be `null` per card → both sources are optional; never
assume one exists.

---

## 6. Resolving a specific card to its price (verified strategy)

The docs say "best key: `set_id` + `card_number`". **That is only true for positive `set_id`s.**
Live-verified 2026-10-02: several sets carry a **negative `set_id`** in the `/sets` index
(e.g. Lost Thunder `LOT = -113`, Ancient Roar `CS5.1C = -38`, Wild Force `CS6.1C = -42`,
Gem Pack Vol.4 `CBB4C = -240`, Gem Pack Vol.5 `CBB5C = -242`). Querying those ids returns
**unrelated cards that merely share the card number**:

| Docs method → what it returns | The key that actually works |
|---|---|
| `q="-113 54"` → `Shelgon 054/113 (Delta Species)` ❌ | `q="lot 54"` → `Slowpoke [LOT 54]` ✅ |
| `q="-38 90"` → `Staryu (SV4a)` ❌ | `q="ancient roar 90"` → `Roaring Moon ex - 090/066 [SV4K] $40.63` ✅ |
| `q="-42 80"` → `Medicham ex (SV07)` ❌ | `q="wild force 80"` → `Gastly - 080/071 [SV5K] $37.36` ✅ |

Also verified:

- `q="cs5.1c 90"` (using `set_code`) → **0 results** — the Chinese set code is not searchable.
- The **canonical set name** *is* searchable and selects the right printing.
- A card's `card_info.name` is often `"<name> - <number> (<set>)"` (e.g. `"Roaring Moon ex - 090/066"`),
  and `card_info.set_id` may be the *real* upstream id (Ancient Roar JP = `SV4K`/`23610`), **not** the
  index's `-38` — so the numeric id cannot be trusted for validation either.

### 6.1 The strategy the fetcher uses (`pokewallet/fetch_prices.py`)

For each portfolio card, try up to three query keys, **validating every candidate**:

1. `"{set_id} {number}"` — the docs' method, exact for positive ids;
2. `"{set_code} {number}"` — rescue for some sets;
3. `"{canonical set name} {number}"` — the reliable key for negative-id / Chinese / JP sets.

A candidate is accepted **only if the card number agrees** *and* at least one identity signal agrees:
the normalised card name (parenthetical- and `" - <num>"`-stripped) is identical, **or** the card's
`set_code`/`set_id` equals the expected one. Requiring the name is what stops the free-text `/search`
from matching an unrelated card that merely shares a number. **A wrong match silently corrupts the
portfolio, so an unmatched card is always preferred over a confidently-wrong one** (decision D7).
Rejected candidates are still recorded (the snapshot `candidate` column), never discarded.

### 6.2 Pricing without a per-card call is impossible on the free plan

- `GET /sets/:code` → cards come back with **empty** `prices[]` arrays (bulk pricing is `/prices/:setCode`, PRO).
- `GET /cards/:id` → carries prices, but you must already know the id.
- `GET /search?q="<key> <number>"` → returns the card **with** TCGPlayer/CardMarket prices. ✅

So the fetcher spends **one `/search` call per card** (2–3 when the first key finds nothing) and builds
history by re-running on a schedule. Rate math: 175 portfolio cards ≈ 175–200 calls, which exceeds the
100/hour cap → the run is split across hourly windows by `pokewallet/fetch_loop.py`.

### 6.3 Resume & merge (so re-runs don't waste the budget)

`fetch_prices.py` reads its own append-only `snapshots/portfolio_prices.jsonl` on start:

- a card fetched within `--fresh-hours` (default 20) is **served from cache with no API call**;
- a card whose fresh fetch fails keeps its **last-known price** (never erased);
- every row is labelled `served_from` ∈ {`fetched`, `cache`, `cache-fallback`, `miss`, `orphan`}.

---

## 7. FINN → PokeWallet matching (`finn/finn_matcher.py`)

Turns a FINN heading / search record / parsed ad into ranked PokeWallet candidates + prices and the
**overlay payload** the browser tool (M9) consumes. Same caution as §6, but expressed as a *score*:

- **Heading parse** — card number (`#101`, `101/102`, trailing), year, parenthetical set/variant
  hints, and an inline **set suffix** peeled off via the cached set index
  (`"Psychic Energy Base Set"` → name `Psychic Energy`, set `Base Set`).
- **Query plan** — most-precise first: `"<name> <num>"`, `"<set> <num>"`, canonical set name
  (`pwlib.sets.lookup`) `+ <num>`, then bare name/set. Stops after the first query with hits.
- **Scoring** — number agreement + name agreement (exact / token-overlap) + set agreement + price
  presence. `best` only when `score ≥ 60` **and** the number agrees (D7: unmatched ≫ confidently-wrong).
- **Cache** — append-only `data/finn/_cache/query_cache.jsonl` (newest-wins, normalised-query key,
  `--cache-hours` TTL). Repeat lookups cost **zero** calls; `--offline` reads the cache only.
- **Output** — append-only `data/finn/matches/matches.jsonl` + timestamped `overlay_<ts>.json`
  (`--json` to stdout): `parsed`, `queries`, `candidates[]`, `best`, `value{ … estimated:true }`,
  and a **stored-but-unconfirmed** `pricecharting_url`.
- **Budget** — `--max-calls` caps spend; shares the same 100/hr free budget as everything else.

---

## 8. Change log for this file

| Date | Change |
|---|---|
| 2026-10-02 | Created: version, rate limits, endpoint availability, cache TTLs, response shape, discrepancies. |
| 2026-10-02 | §6 rewritten: proved `set_id`+number is broken for negative ids; documented the multi-key + per-candidate validation strategy, per-card pricing, and the resume/merge behavior. |
| 2026-10-02 | §7 added: FINN→PokeWallet matcher strategy (heading parse + set-suffix, query plan, scoring, offline-safe query cache, overlay payload). Changelog renumbered to §8. |
