# PokeWallet API — Live-Verified Notes

> Companion to [`pokewallet_io_api-docs.md`](pokewallet_io_api-docs.md). Everything here was observed
> against the **live** API, not copied from the docs. When the docs and this file disagree, **this file
> wins** (the docs are behind the deployed build).
>
> **Verified:** 2026-10-02 · **Environment:** `API_KEY_POKEWALLET` set · **Client:** `curl` / Python.
> Raw captures backing these notes live in [`../data/pokewallet/_smoke/`](../data/pokewallet/_smoke/).

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

## 6. Lookup guidance

- **Best key:** `set_id` + `card_number` together, e.g. `/search?q=23520 004`.
- Prefer `set_id` over `set_code` (see §5.1).
- Name-only search is noisy (e.g. `pikachu` → 821 results) — use it only for fuzzy candidate ranking,
  never as the sole resolver.

---

## 7. Change log for this file

| Date | Change |
|---|---|
| 2026-10-02 | Created: version, rate limits, endpoint availability, cache TTLs, response shape, discrepancies. |
