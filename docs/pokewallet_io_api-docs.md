[### PokeWallet API](/)

[![](/images/op-skull.svg)One Piece API](/berrywallet)  [Catalog](/catalog) [Support Us](https://ko-fi.com/pokewallet) [Sign In](/auth/login?source=pokemon)

[Introduction](#introduction)  [Quick Start](#quick-start)  [Authentication](#authentication)  [Rate Limits](#rate-limits)  [Card ID Formats](#card-id-formats)  [Price Variants](#price-variants)

API Reference

 [Public Endpoints](#public-endpoints)

[`GET /health`](#endpoint-health)[`GET /`](#endpoint-root)

 [Search Endpoints](#search-endpoints)

[`GET /search`](#endpoint-search)[`GET /search/by-price-range`SOON](#endpoint-search-by-price-range)[`GET /search/by-type`SOON](#endpoint-search-by-type)

 [Cards Endpoints](#cards-endpoints)

[`GET /cards/:id`](#endpoint-cards-id)[`GET /cards/:id/price-history`PRO](#endpoint-cards-price-history)

 [Sets Endpoints](#sets-endpoints)

[`GET /sets`](#endpoint-sets)[`GET /sets/:setCode`](#endpoint-sets-setcode)[`GET /sets/:setCode/image`](#endpoint-sets-image)[`GET /sets/:setCode/statistics`PRO](#endpoint-sets-statistics)[`GET /sets/trending`PRO](#endpoint-sets-trending)[`GET /sets/:setCode/completion-value`PRO](#endpoint-sets-completion-value)

 [Prices Endpoints](#prices-endpoints)

[`GET /prices/:setCode`PRO](#endpoint-prices)

 [Analytics Endpoints](#analytics-endpoints)

[`GET /analytics/top-cards`PRO](#endpoint-analytics-top-cards)

 [Images Endpoint](#images-endpoint)

[`GET /images/:id`](#endpoint-images)

![One Piece](/images/op-skull.svg) One Piece API

 [One Piece API Docs →](/berrywallet-docs)

[Code Examples](#examples)  [Error Handling](#errors)  [Best Practices](#best-practices)

📚 Documentation

# PokéWallet API Documentation

Complete REST reference for the most comprehensive Pokémon TCG platform. Real-time pricing, 50,000+ cards database, and generous rate limits.

👨‍🍳Still cooking – Taste it while it's hot!

**50,000+ Cards**Complete TCG Database

**Real-Time Pricing**TCGPlayer & CardMarket

**Fast & Reliable**Global CDN, <100ms latency

**Base URL:**`https://api.pokewallet.io`

## Quick Start

Get started with PokéWallet API in 4 simple steps:

1

### Create an Account

Sign up for free to start using the API. Upgrade anytime from your dashboard.

 [Sign Up Now](/auth/login?source=pokemon)

2

### Generate an API Key

Create your first API key from the dashboard.

3

### Make Your First Request

Start querying the API with your key.

cURL

```
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/search?q=charizard"
```

4

### Join the Discord Community

Stay up to date with new features, ask for help, and connect with other developers.

 [Join Discord](https://discord.gg/znDxEjmDVP)

## Authentication

All API requests (except `/health`) require authentication using an API key.

### API Key Format

API keys follow this format:

* **Production keys:** `pk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
* **Development keys:** `pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

**Security Warning:** Never expose your API keys in client-side code, public repositories, or logs. Always use environment variables.

### Authentication Methods

You can authenticate using either the `X-API-Key` header or `Authorization` header:

X-API-Key Header (Recommended)

```
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/search?q=pikachu"
```

Authorization Header

```
curl -H "Authorization: Bearer pk_live_your_key_here" \
     "https://api.pokewallet.io/search?q=pikachu"
```

## Rate Limits

Rate limits vary depending on your subscription plan:

| Plan | Hourly Limit | Daily Limit | Price |
| --- | --- | --- | --- |
| Free | 100 requests | 1,000 requests | $0/month |
| Early Access ⭐ | 1,000 requests | 10,000 requests | *No longer available* |
| Coffee ☕ | 1,000+ requests | 10,000+ requests | Buy a coffee on Ko-fi |
| Pro | **5,000 requests** | **50,000 requests** | **€20/month** |
| Business | Custom | Custom | Contact us |

All new users start on the **Free plan**. Upgrade from your [dashboard](/dashboard).
Early Access was our initial launch tier and is no longer available for new users.

**Please note:** After upgrading your plan, activation may require a couple of hours.

[See all plans, pricing and FAQs](/pricing)

### Rate Limit Headers

Every API response includes rate limit information:

```
X-RateLimit-Limit-Hour: 100
X-RateLimit-Remaining-Hour: 95
X-RateLimit-Limit-Day: 1000
X-RateLimit-Remaining-Day: 823
```

### Rate Limit Exceeded (429)

When you exceed your rate limit, you'll receive a `429 Too Many Requests` response:

```
{
  "error": "Rate limit exceeded",
  "message": "Hourly limit exceeded",
  "limits": {
    "hourly": {
      "limit": 100,
      "used": 100,
      "remaining": 0
    },
    "daily": {
      "limit": 1000,
      "used": 523,
      "remaining": 477
    }
  }
}
```

## Card ID Formats

The API uses two different ID formats depending on the card's data source:

### TCG Cards (TCGPlayer)

pk\_ + hash

**Format:** `pk_` + hexadecimal hash

**Example:**

```
pk_72046138a4c1908a9f27c93fdd8189ba...
```

**Usage:** All cards with TCGPlayer data (even if they also have CardMarket data)

### CardMarket-Only Cards

No prefix

**Format:** Direct hexadecimal hash (no `pk_` prefix)

**Example:**

```
2208e8a2750c07d89e54870ffcef80d1...
```

**Usage:** Only cards exclusively from CardMarket (e.g., Japanese sets, European promos)

**Unique Variants:** Cards with the same `card_number` but different variants (V1, V2, etc.) have unique IDs.

## Price Variants

Prices come from two different sources, each with its own way of classifying card variants. Understanding this distinction is important when reading the `prices` array in any response.

### TCGPlayer

🇺🇸 USA

sub\_type\_name

Uses a `sub_type_name` field to distinguish versions:

|  |  |
| --- | --- |
| `Normal` | Common / non-holo cards |
| `Holofoil` | Holo cards |
| `Reverse Holofoil` | Most Vintage Sets (Base through Neo) |
| `1st Edition` | Base Set 1st Ed and similar |
| `Unlimited` | Standard version of sets that have 1st editions |
| `Shadowless` | Specific Base Set variants |

### CardMarket

🇪🇺 Europe

variant\_type

Uses a simpler `variant_type` field:

|  |  |
| --- | --- |
| `normal` | Standard non-holo version |
| `holo` | Holo version |

CardMarket uses a simpler two-tier system regardless of the set era.

## Public Endpoints

**No Authentication Required:** These endpoints are publicly accessible.

GET`/health`No Auth Required

Check API status, database, cache, and storage health with response times.

#### Example Request:

cURL

```
curl "https://api.pokewallet.io/health"
```

#### Response Example (Healthy):

200 OK

```
{
  "status": "healthy",
  "timestamp": "2025-12-16T10:30:00.000Z",
  "version": "1.1.0",
  "checks": {
    "database": {
      "status": "healthy",
      "responseTime": 45
    },
    "cache": {
      "status": "healthy",
      "responseTime": 3
    },
    "storage": {
      "status": "healthy",
      "responseTime": 12
    }
  },
  "responseTime": 60,
  "region": "FRA"
}
```

#### Response Example (Unhealthy):

503 Service Unavailable

```
{
  "status": "unhealthy",
  "timestamp": "2025-12-16T10:30:00.000Z",
  "version": "1.1.0",
  "message": "Critical services unavailable - API may not function correctly",
  "checks": {
    "database": {
      "status": "unhealthy",
      "responseTime": null,
      "message": "Connection failed"
    },
    "cache": {
      "status": "healthy",
      "responseTime": 3
    },
    "storage": {
      "status": "healthy",
      "responseTime": 12
    }
  },
  "responseTime": 1050,
  "region": "FRA"
}
```

GET`/`No Auth Required

Get API information, version, and available endpoints.

#### Example Request:

cURL

```
curl "https://api.pokewallet.io/"
```

#### Response Example:

200 OK

```
{
  "name": "PokeWallet API",
  "version": "1.1.0",
  "status": "production",
  "authentication": {
    "required": true,
    "method": "API Key",
    "header": "X-API-Key",
    "format": "pk_live_xxxxxxxxxxxxx"
  },
  "endpoints": {
    "health": { "path": "/health", "auth_required": false },
    "search": { "path": "/search?q=charizard&limit=20", "auth_required": true },
    "cardDetail": { "path": "/cards/:id", "auth_required": true },
    "sets": { "path": "/sets", "auth_required": true },
    "setDetails": { "path": "/sets/:setCode?page=1&limit=50", "auth_required": true },
    "images": { "path": "/images/:id?size=high", "auth_required": true }
  },
  "rate_limits": {
    "per_hour": 100,
    "per_day": 1000,
    "plan": "free"
  }
}
```

## Search Endpoints

**Authentication Required:** All Search endpoints require an API key.

GET`/search`

Advanced card search with unified pricing from TCGPlayer and CardMarket.

#### Parameters:

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `q` | string | Required | Search query. Supports multiple formats:  * **Card name:** `charizard`, `pikachu ex` * **Set code:** `SV2a`, `SWSH3` * **Card number:** `148`, `148/165` * **set\_id + card number:** `24541 148` — precise lookup using a numeric set ID and card number |
| `page` | number | Optional | Page number (default: 1) |
| `limit` | number | Optional | Results per page (default: 20, max: 100) |

#### Example Requests:

cURL — Search by name

```
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/search?q=charizard+ex"
```

cURL — Search by set\_id + card number (precise lookup)

```
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/search?q=24541%20148"
```

#### Response Example (TCG Card):

200 OK

```
{
  "query": "pikachu",
  "results": [
    {
      "id": "pk_72046138a4c1908a9f27c93fdd8189ba4ac8e683efaed6b9161efcef129302394a9ec1d20d",
      "card_info": {
        "name": "Pikachu ex (Pikachu 60)",
        "clean_name": "Pikachu ex Pikachu 60",
        "set_name": "Battle Academy 2024",
        "set_code": "BA2024",
        "set_id": "23520",
        "card_number": "106",
        "rarity": "Holo Rare",
        "card_type": "Lightning",
        "hp": "200.0",
        "stage": "Basic",
        "card_text": null,
        "attacks": ["[LLC] Thunderbolt (120)"],
        "weakness": "Fx2",
        "resistance": null,
        "retreat_cost": "1.0"
      },
      "images": {
        "languages": ["en", "it", "de"]
      },
      "tcgplayer": {
        "prices": [{
          "sub_type_name": "Normal",
          "low_price": 7,
          "mid_price": 9.37,
          "high_price": 18,
          "market_price": 8.01,
          "direct_low_price": null,
          "updated_at": "2025-12-27T05:14:43.451818"
        }],
        "url": "https://www.tcgplayer.com/product/556443"
      },
      "cardmarket": null
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 56,
    "total_pages": 3
  },
  "metadata": {
    "total_count": 56,
    "tcg": 18,
    "cardmarket": 38,
    "tcg_only": 18,
    "cardmarket_only": 38,
    "both_sources": 0
  }
}
```

#### Response Example (CardMarket-Only Card):

200 OK

```
{
  "query": "cubone cbb3c",
  "results": [
    {
      "id": "8eb728bd59d4e1a0d94c354e4cc65a7465b55cfa4261bfa93301faa5ec921f97",
      "card_info": {
        "name": "Cubone (CBB3C 04)",
        "set_code": "CBB3C",
        "set_id": "-15",
        "card_number": "4"
      },
      "images": {
        "languages": ["en"]
      },
      "tcgplayer": null,
      "cardmarket": {
        "product_name": "Cubone (CBB3C 04)",
        "prices": [
          {
            "avg": null,
            "low": 0.02,
            "avg1": null,
            "avg7": null,
            "avg30": null,
            "trend": 0,
            "updated_at": "2025-12-29T04:54:57.728497",
            "variant_type": "normal"
          },
          {
            "avg": 0.37,
            "low": 0.02,
            "avg1": 0.1,
            "avg7": 0.35,
            "avg30": 0.35,
            "trend": 0.29,
            "updated_at": "2025-12-29T04:54:57.728497",
            "variant_type": "holo"
          }
        ],
        "product_url": "https://www.cardmarket.com/en/Pokemon/Products/Singles/Gem-Pack-Vol-3/Cubone-V1-CBB3C04"
      }
    },
    {
      "id": "a7ed43b641d4f24b494ad5889845085f33966d1f19cb9e0ed353979025d8da31",
      "card_info": {
        "name": "Cubone (CBB3C 04)",
        "set_code": "CBB3C",
        "set_id": "-15",
        "card_number": "4"
      },
      "images": {
        "languages": ["en"]
      },
      "tcgplayer": null,
      "cardmarket": {
        "product_name": "Cubone (CBB3C 04)",
        "prices": [
          {
            "avg": null,
            "low": 0.02,
            "trend": 0,
            "variant_type": "normal"
          }
        ],
        "product_url": "https://www.cardmarket.com/en/Pokemon/Products/Singles/Gem-Pack-Vol-3/Cubone-V4-CBB3C04"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 2,
    "total": 7,
    "total_pages": 4
  },
  "metadata": {
    "total_count": 7,
    "tcg": 0,
    "cardmarket": 7,
    "tcg_only": 0,
    "cardmarket_only": 7,
    "both_sources": 0
  }
}
```

**Note on CardMarket-Only Cards:** The 7 Cubone variants (V1-V7) all share the same `card_number: "4"` and `set_code: "CBB3C"`, but each has a unique ID. This ensures each variant can be uniquely identified and its correct image can be retrieved.

**Consistent Set Identifiers:** The `set_code` and `set_id` fields in `card_info` are the same canonical values returned by the `/sets` endpoint. You can use `set_id` to reliably match cards to their set across all endpoints.

**Image Languages:** The `images.languages` array lists the languages the card's image is available in. `"en"` is always present and refers to the card's default artwork (English for international sets, Japanese for Japanese sets); additional codes (`it`, `fr`, `de`, `es`, `pt`) mean a localized European variant can be requested via `/images/:id?lang=xx`. See the [Images Endpoint](#images-endpoint).

GET`/search/by-price-range`Coming Soon

Search cards by price range with optional filters for rarity and set.

**⏳ This endpoint is currently in development** and will be available soon after thorough testing.

GET`/search/by-type`Coming Soon

Search cards by card type (Pokemon, Trainer, Energy) and optional subtype filters.

**⏳ This endpoint is currently in development** and will be available soon after thorough testing.

## Cards Endpoints

**Authentication Required:** All Cards endpoints require an API key in the `X-API-Key` header.

GET`/cards/:id`

Get complete card details with unified pricing from TCGPlayer and CardMarket.

#### Parameters:

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | string | Required | Card ID - Two formats supported:  * **TCG cards:** `pk_xxx` (with prefix) * **CardMarket-only:** hexadecimal hash (no prefix) |
| `set_code` | string | Optional | Set code for disambiguation (e.g., "SWSH3", "SV1", "CBB3C"). Supports both alphanumeric codes and numeric group IDs. |

#### Example Request:

cURL

```
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/cards/pk_xxx"
```

#### Response Example:

200 OK

```
{
  "id": "pk_xxx",
  "card_info": {
    "name": "Charizard VMAX",
    "clean_name": "Charizard VMAX",
    "set_name": "Darkness Ablaze",
    "set_code": "SWSH3",
    "set_id": "22789",
    "card_number": "20/189",
    "rarity": "Secret Rare",
    "card_type": "Pokemon",
    "hp": "330",
    "stage": null,
    "card_text": "VMAX rule: When your VMAX Pokemon is Knocked Out...",
    "attacks": ["Fire Spin - 320 damage"],
    "weakness": "Water",
    "resistance": null,
    "retreat_cost": "3"
  },
  "images": {
    "languages": ["en", "it", "fr", "de", "es"]
  },
  "tcgplayer": {
    "url": "https://tcgplayer.com/product/123456",
    "prices": [
      {
        "sub_type_name": "Normal",
        "low_price": 245.99,
        "mid_price": 299.99,
        "high_price": 450.00,
        "market_price": 285.00,
        "direct_low_price": 250.00,
        "updated_at": "2025-12-16T04:00:00Z"
      }
    ]
  },
  "cardmarket": {
    "product_name": "Charizard VMAX (Secret)",
    "product_url": "https://cardmarket.com/product/789012",
    "prices": [{
      "variant_type": "normal",
      "avg": 260.50,
      "low": 240.00,
      "trend": 270.00,
      "avg1": 258.30,
      "avg7": 255.80,
      "avg30": 280.50,
      "updated_at": "2025-12-16T04:00:00Z"
    }]
  }
}
```

GET`/cards/:id/price-history`Pro

Get historical price snapshots from both TCGPlayer and CardMarket, with percentage changes over 7, 14, 30, 60 and 120 days.

**Pro feature — 7-day free trial available.** Activate your free trial from the [dashboard](/dashboard) to access this endpoint at no cost.

#### Parameters:

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | string | Required | Card ID (`pk_xxx` for TCG+CM cards, `encrypted_id` for CM-only cards) |

#### Example Request:

cURL

```
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/cards/pk_xxx/price-history"
```

#### Response Example:

200 OK

```
{
  "id": "pk_abc123",
  "card_name": "Charizard (Base Set)",
  "tcgplayer": {
    "variants": {
      "Normal": {
        "current": { "market": 12.50, "low": 10.00, "mid": 11.50, "high": 15.00, "direct_low": 11.00 },
        "price_7d": 11.80,
        "price_14d": 11.20,
        "price_30d": null,
        "price_60d": null,
        "price_120d": null,
        "change_7d": "+5.9%",
        "change_14d": "+11.6%",
        "change_30d": null,
        "change_60d": null,
        "change_120d": null,
        "last_updated": "2026-04-26T06:00:00Z"
      }
    }
  },
  "cardmarket": {
    "variants": {
      "normal": {
        "current": { "avg": 9.50, "low": 8.00, "trend": 9.20 },
        "avg_1d": 9.40,
        "avg_7d": 8.90,
        "avg_30d": 8.50,
        "price_7d": 8.90,
        "price_14d": 8.60,
        "price_30d": null,
        "price_60d": null,
        "price_120d": null,
        "change_7d": "+6.7%",
        "change_14d": "+10.5%",
        "change_30d": null,
        "change_60d": null,
        "change_120d": null,
        "last_updated": "2026-04-26T06:00:00Z"
      }
    }
  }
}
```

Fields like `price_14d`, `price_30d`, `price_60d`, `price_120d` return `null` until enough weekly snapshots have accumulated. `price_7d` is available from April 16, 2026.

#### Trial Response Headers:

When accessing this endpoint during an active trial, two extra headers are included:

```
X-Trial-Expires-At: 2026-05-01T00:00:00.000Z
X-Trial-Days-Remaining: 7
```

#### Error Responses:

| Status | Description |
| --- | --- |
| `403` — trial not activated | `{ "error": "Trial not activated", "redeem_url": "https://pokewallet.io/dashboard" }` |
| `403` — trial expired | `{ "error": "Pro plan required", "upgrade_url": "https://pokewallet.io/pricing" }` |

## Sets Endpoints

**Authentication Required:** All Sets endpoints require an API key.

GET`/sets`

Get list of all Pokemon sets with card counts.

#### Response Fields:

| Field | Type | Description |
| --- | --- | --- |
| `name` | string | Set name |
| `set_code` | string | null | Short code for the set (e.g., "SV1", "SWSH3"). May be `null` for some promo or special sets. |
| `set_id` | string | Unique numeric identifier for the set (group\_id) |
| `card_count` | number | Total number of unique cards in the set |
| `language` | string | null | Set language code (e.g., "eng", "jap", "ger"). May be `null` if not specified. |
| `release_date` | string | null | Set release date (e.g., "3rd August, 2007"). May be `null` if unknown. |

#### Example Request:

```
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/sets"
```

#### Response Example:

200 OK

```
{
  "success": true,
  "data": [
    {
      "name": "Scarlet & Violet",
      "set_code": "SV1",
      "set_id": "23456",
      "card_count": 198,
      "language": "eng",
      "release_date": "31st March, 2023"
    },
    {
      "name": "Silver Tempest",
      "set_code": "SWSH12",
      "set_id": "23123",
      "card_count": 245,
      "language": "eng",
      "release_date": "11th November, 2022"
    },
    {
      "name": "Vaporeon VMAX Promo",
      "set_code": null,
      "set_id": "24073",
      "card_count": 1,
      "language": "jap",
      "release_date": null
    }
  ],
  "total": 150
}
```

GET`/sets/:setCode`

Get set details with paginated card list.

#### Parameters:

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `setCode` | string | Required | Set identifier - accepts either `set_code` (e.g., "SWSH3", "SV1") or `set_id` (e.g., "23456"). Both values are returned by the `/sets` endpoint. |
| `page` | number | Optional | Page number (default: 1) |
| `limit` | number | Optional | Results per page (default: 50, max: 200) |
| `language` | string | Optional | Filter by language when a `set_code` matches multiple sets (e.g., `eng`, `jap`, `chn`). Not needed when using a numeric `set_id`. |

#### Set Object Fields:

| Field | Type | Description |
| --- | --- | --- |
| `name` | string | Set name |
| `set_code` | string | null | Short code for the set. May be `null` for some promo sets. |
| `set_id` | string | Unique numeric identifier for the set (group\_id) |
| `total_cards` | number | Total number of unique cards in the set |
| `language` | string | null | Set language code (e.g., "eng", "jap"). May be `null` if not specified. |
| `release_date` | string | null | Set release date (e.g., "3rd August, 2007"). May be `null` if unknown. |

#### Example Request:

```
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/sets/SWSH3"
```

#### Response Example:

200 OK

```
{
  "success": true,
    "set": {
        "name": "Plasma Freeze",
        "set_code": "PLF",
        "set_id": "1382",
        "total_cards": 123,
        "language": "eng",
        "release_date": "8th May, 2013"
    },
    "cards": [
        {
            "id": "pk_4687f4c4a0499fd6a7fa267a9bef2cb4c462f19478522c5a85eaf116ca1d1f0c8ad2ba5fc8ac3c668627bce5",
            "card_info": {
                "name": "Weedle",
                "clean_name": "Weedle",
                "set_name": "Plasma Freeze",
                "set_code": "1382",
                "card_number": "1/116",
                "rarity": "Common",
                "card_type": null,
                "hp": "50.0",
                "stage": "Basic",
                "card_text": null,
                "attacks": [
                    "[G] Triple Stab (10x) Flip 3 coins.  This attack does 10 damage times the number of heads."
                ],
                "weakness": "Rx2",
                "resistance": null,
                "retreat_cost": "1.0"
            },
            "images": {
                "languages": ["en"]
            },
            "tcgplayer": {
                "prices": [],
                "url": "https://www.tcgplayer.com/product/90547"
            },
            "cardmarket": {
                "product_name": "Weedle (PLF 1)",
                "prices": [],
                "product_url": "https://www.cardmarket.com/en/Pokemon/Products/Singles/Plasma-Freeze/Weedle-PLF1"
            }
        }
```

#### Disambiguation Response:

Some set codes (e.g., `"PR"`) are shared by multiple sets with different `set_id`s. When this happens, instead of returning a single set, the API returns a disambiguation response listing all matching sets so you can pick the right one.

200 OK — Multiple matches

```
{
  "disambiguation": true,
  "message": "Multiple sets found for set_code 'PR'. Use set_id to specify which one.",
  "matches": [
    {
      "set_id": "1938",
      "set_code": "PR",
      "name": "Alternate Art Promos",
      "language": "eng",
      "release_date": null
    },
    {
      "set_id": "1451",
      "set_code": "PR",
      "name": "XY Promos",
      "language": "eng",
      "release_date": null
    },
    {
      "set_id": "1407",
      "set_code": "PR",
      "name": "Black and White Promos",
      "language": "eng",
      "release_date": null
    }
  ],
  "total": 21
}
```

**Tip:** When you receive a disambiguation response, pick the `set_id` of the set you need and call `/sets/1938` (using the numeric `set_id`) to get that specific set with its cards.

GET`/sets/:setCode/image`

Retrieve the logo/image for a set. Returns binary image data (PNG). Not all sets have an image available.

#### Parameters:

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `setCode` | string | Required | Set identifier — accepts either `set_code` (e.g., `SWSH3`) or numeric `set_id` (e.g., `23456`). Both are returned by the `/sets` endpoint. |
| `language` | string | Optional | Required only when a `set_code` is shared by multiple sets (e.g., `eng`, `jap`). Not needed when using a numeric `set_id`. |

#### Response Headers:

* `Content-Type`: `image/png`
* `Cache-Control`: `public, max-age=86400`

#### Example Request:

```
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/sets/SWSH3/image" \
     --output swsh3.png
```

#### Error Responses:

404 — Image not available

```
{
  "error": "Image not available",
  "message": "No set image is available for this set."
}
```

409 — Ambiguous set code

```
{
  "error": "Ambiguous set code",
  "message": "Multiple sets found for set_code 'SM11'. Add ?language=eng (or jap, etc.) to disambiguate, or use a numeric set_id.",
  "matches": [
    { "set_id": "2464", "language": "eng" },
    { "set_id": "23690", "language": "jap" }
  ]
}
```

**Tip:** Use a numeric `set_id` (e.g., `/sets/23456/image`) to always get a unique result without disambiguation.

GET`/sets/:setCode/statistics`PRO

Get complete price statistics and rarity breakdown for a set. Returns average, min and max prices from both TCGPlayer (USD) and CardMarket (EUR), plus the most expensive card and a 7-day trend direction.

**Pro feature — 7-day free trial available.** Activate your free trial from the [dashboard](/dashboard) to access this endpoint at no cost.

#### Parameters:

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `setCode` | string | Required | Numeric group\_id (`23599`) or alphanumeric set code (`sv2a`) |
| `variant` | string | Optional | Filter CardMarket prices by variant: `normal`, `holo`. Does not affect TCGPlayer data. |

#### Example Request:

cURL

```
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/sets/23599/statistics"
```

#### Response Example:

200 OK

```
{
  "set_info": {
    "name": "SV2a_ Pokemon Card 151",
    "set_code": "23599",
    "total_cards": 524
  },
  "price_statistics": {
    "tcgplayer": {
      "avg_market_price": "7.80",
      "min_price": 0.07,
      "max_price": 307.56,
      "most_expensive": { "name": "Charizard ex - 201/165", "price": 307.56 }
    },
    "cardmarket": {
      "avg_price": "2.34",
      "min_price": 0.37,
      "max_price": 17.91,
      "trend_direction": "up"
    }
  },
  "rarity_breakdown": {
    "Common": 199,
    "Uncommon": 186,
    "Rare": 77,
    "Double Rare": 12,
    "Art Rare": 18,
    "Super Rare": 16,
    "Special Art Rare": 8,
    "Ultra Rare": 3,
    "Unknown": 5
  }
}
```

#### Trial Response Headers:

When accessing this endpoint during an active trial, two extra headers are included:

```
X-Trial-Expires-At: 2026-05-01T00:00:00.000Z
X-Trial-Days-Remaining: 7
```

#### Error Responses:

| Status | Description |
| --- | --- |
| `403` — trial not activated | `{ "error": "Trial not activated", "redeem_url": "https://pokewallet.io/dashboard" }` |
| `403` — trial expired | `{ "error": "Pro plan required", "upgrade_url": "https://pokewallet.io/pricing" }` |

GET`/sets/trending`PRO

Returns the sets with the highest average price variation over the last 7 or 30 days, based on CardMarket moving averages. Each set includes the top movers (individual cards with the largest price change).

**Pro feature — 7-day free trial available.** Activate your free trial from the [dashboard](/dashboard) to access this endpoint at no cost.

#### Parameters:

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `period` | string | Optional | Time window: `7d` (default) or `30d` |
| `limit` | number | Optional | Number of sets to return (default: 10, max: 50) |

#### Example Request:

cURL

```
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/sets/trending?period=7d&limit=5"
```

#### Response Example:

200 OK

```
{
  "period": "7d",
  "trending_sets": [
    {
      "set_name": "Miracle of the Desert",
      "set_code": "-4",
      "card_count": 46,
      "cardmarket": {
        "price_change": "+90.6%",
        "avg_price_current": 15.67,
        "avg_price_previous": 8.22,
        "top_movers": [
          { "name": "Dusclops (ADV2 031)", "change": "+449.1%" },
          { "name": "Raichu ex (ADV2 023)", "change": "+433.3%" },
          { "name": "Typhlosion ex (ADV2 013)", "change": "+389.4%" }
        ]
      },
      "tcgplayer": null
    },
    {
      "set_name": "BW1_ Black Collection",
      "set_code": "23893",
      "card_count": 18,
      "cardmarket": {
        "price_change": "+40.8%",
        "avg_price_current": 2.22,
        "avg_price_previous": 1.58,
        "top_movers": [
          { "name": "Beartic (BW1b 018)", "change": "+171.2%" },
          { "name": "Emboar (BW1b 010)", "change": "+97.4%" },
          { "name": "Sawsbuck (BW1b 007)", "change": "-86.3%" }
        ]
      },
      "tcgplayer": {
        "status": "work_in_progress",
        "message": "TCGPlayer price history not yet available"
      }
    }
  ]
}
```

#### Trial Response Headers:

When accessing this endpoint during an active trial, two extra headers are included:

```
X-Trial-Expires-At: 2026-05-01T00:00:00.000Z
X-Trial-Days-Remaining: 7
```

#### Error Responses:

| Status | Description |
| --- | --- |
| `403` — trial not activated | `{ "error": "Trial not activated", "redeem_url": "https://pokewallet.io/dashboard" }` |
| `403` — trial expired | `{ "error": "Pro plan required", "upgrade_url": "https://pokewallet.io/pricing" }` |

GET`/sets/:setCode/completion-value`PRO

Calculates the estimated cost to complete a set by buying one copy of every card. Returns separate estimates for TCGPlayer (USD) and CardMarket (EUR) — no cross-currency conversion is performed. Includes a breakdown by rarity.

**Pro feature — 7-day free trial available.** Activate your free trial from the [dashboard](/dashboard) to access this endpoint at no cost.

#### Parameters:

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `setCode` | string | Required | Numeric group\_id (`23599`) or alphanumeric set code (`sv2a`). CardMarket-only sets (negative group\_id) return 404. |

#### Example Request:

cURL

```
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/sets/23599/completion-value"
```

#### Response Example:

200 OK

```
{
  "set_info": {
    "name": "SV2a_ Pokemon Card 151",
    "set_code": "23599",
    "total_cards": 524
  },
  "completion_cost": {
    "tcgplayer": {
      "currency": "USD",
      "low_estimate": 4516.16,
      "market_estimate": 4056.03,
      "high_estimate": 13687.29
    },
    "cardmarket": {
      "currency": "EUR",
      "low_estimate": 683.50,
      "avg_estimate": 1232.46,
      "trend_estimate": 1526.69
    },
    "note": "TCGPlayer prices in USD, CardMarket prices in EUR. Cross-currency comparison not available."
  },
  "breakdown_by_rarity": {
    "Common": { "count": 199, "total_cost": 950.32 },
    "Uncommon": { "count": 186, "total_cost": 732.37 },
    "Rare": { "count": 77, "total_cost": 645.50 },
    "Double Rare": { "count": 12, "total_cost": 8.29 },
    "Art Rare": { "count": 18, "total_cost": 254.25 },
    "Super Rare": { "count": 16, "total_cost": 85.38 },
    "Special Art Rare": { "count": 8, "total_cost": 893.35 },
    "Ultra Rare": { "count": 3, "total_cost": 31.02 },
    "Unknown": { "count": 5, "total_cost": 12.47 }
  }
}
```

404 — CardMarket-only set

```
{
  "success": false,
  "error": "This is a CardMarket-only set without TCGPlayer pricing data"
}
```

#### Trial Response Headers:

When accessing this endpoint during an active trial, two extra headers are included:

```
X-Trial-Expires-At: 2026-05-01T00:00:00.000Z
X-Trial-Days-Remaining: 7
```

#### Error Responses:

| Status | Description |
| --- | --- |
| `403` — trial not activated | `{ "error": "Trial not activated", "redeem_url": "https://pokewallet.io/dashboard" }` |
| `403` — trial expired | `{ "error": "Pro plan required", "upgrade_url": "https://pokewallet.io/pricing" }` |

## Prices Endpoints

GET`/prices/:setCode`PRO

Returns prices for every card in a Pokémon set, flat list, all variants. Use `?source` to restrict to a single marketplace.

**Pro feature — 7-day free trial available.** Activate your free trial from the [dashboard](/dashboard) to access this endpoint at no cost.

#### Path Parameter:

| Parameter | Type | Examples |
| --- | --- | --- |
| `:setCode` | string or number | `MEW`, `sv2a` (set code, case-insensitive)  |  `22873`, `-188` (numeric group\_id) |

#### Query Parameters:

| Parameter | Type | Required | Values |
| --- | --- | --- | --- |
| `source` | string | No | `tcg` — TCGPlayer only  |  `cm` — CardMarket only  |  omit for both |

#### Example Requests:

cURL

```
# Both sources (default)
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/prices/MEW"

# TCGPlayer only
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/prices/MEW?source=tcg"

# By numeric group_id
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/prices/22873"
```

#### Response Example:

200 OK

```
{
  "success": true,
  "source": "both",
  "set_code": "MEW",
  "group_id": "23237",
  "total": 361,
  "data": [
    {
      "card_number": "001/165",
      "name": "Bulbasaur - 001/165",
      "variant": "Normal",
      "tcgplayer": {
        "low_price": 0.05,
        "mid_price": 0.20,
        "high_price": 2.00,
        "market_price": 0.15,
        "direct_low_price": 0.10,
        "updated_at": "2026-05-04T07:43:36.088579"
      },
      "cardmarket": {
        "avg": 0.10,
        "low": 0.04,
        "trend": 0.09,
        "avg1": 0.08,
        "avg7": 0.09,
        "avg30": 0.11,
        "updated_at": "2026-05-04T06:47:05.90041"
      }
    },
    {
      "card_number": "001/165",
      "name": "Bulbasaur - 001/165",
      "variant": "Reverse Holofoil",
      "tcgplayer": { "market_price": 0.30, ... },
      "cardmarket": null
    }
  ]
}
```

#### Disambiguation (300):

If `:setCode` matches multiple sets (e.g. same code in different languages), a `300` is returned. Pass the numeric `group_id` directly to disambiguate.

300 Multiple Choices

```
{
  "disambiguation": true,
  "message": "Multiple sets found for 'SVI'. Use the numeric group_id to specify which one.",
  "matches": [
    { "group_id": "22873", "set_code": "SVI" },
    { "group_id": "23822", "set_code": "svI" }
  ]
}
```

#### Error Codes:

| HTTP | Condition |
| --- | --- |
| `400` | Invalid `source` value |
| `401` | Missing or invalid API key |
| `403` | Plan does not include this endpoint — upgrade to Pro or activate the 7-day trial |
| `404` | Set not found, or `source=tcg` on a CM-only set |

For CM-only sets (`group_id < 0`): `tcgplayer: null` on all cards and `variant: null`. For Japanese sets, `cardmarket: null` is expected as CM only covers the EU market. Response is cached for 15 minutes.

## Analytics Endpoints

**Authentication Required:** All Analytics endpoints require an API key.

GET`/analytics/top-cards`Pro

Get the top N cards ranked by current price or 7-day percentage growth, from TCGPlayer or CardMarket.

**Pro feature — 7-day free trial available.** Activate your free trial from the [dashboard](/dashboard) to access this endpoint at no cost.

#### Parameters:

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `metric` | string | Optional | Ranking metric. One of `price` (default) or `growth` (7-day % change). Any other value returns 400. |
| `source` | string | Optional | Price source. One of `tcg` (default) or `cm`. Any other value returns 400. |
| `limit` | number | Optional | Number of results to return (default: 20, max: 100). |

#### Example Request:

cURL

```
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/analytics/top-cards?metric=growth&source=cm&limit=10"
```

#### Response Example — `metric=price&source=tcg`:

200 OK

```
{
  "metric": "price",
  "source": "tcg",
  "top_cards": [
    {
      "id": "pk_abc123",
      "card_info": {
        "name": "Charizard VSTAR",
        "set_name": "Brilliant Stars",
        "card_number": "018/172",
        "rarity": "Ultra Rare"
      },
      "current_price": 42.50
    }
  ]
}
```

#### Response Example — `metric=growth&source=cm`:

200 OK

```
{
  "metric": "growth",
  "source": "cm",
  "top_cards": [
    {
      "id": "pk_def456",
      "card_info": {
        "name": "Charizard ex (SV3 125)",
        "set_code": "SV3",
        "card_number": "125"
      },
      "current_price": 18.50,
      "change_7d": "+54.2%"
    }
  ]
}
```

`metric=growth` ranks by 7-day change. For `source=tcg` uses `price_7d` snapshots — cards without 7-day history are excluded. For `source=cm` uses CardMarket's native `avg7`.

#### Trial Response Headers:

When accessing this endpoint during an active trial, two extra headers are included:

```
X-Trial-Expires-At: 2026-05-01T00:00:00.000Z
X-Trial-Days-Remaining: 7
```

#### Error Responses:

| Status | Description |
| --- | --- |
| `403` — trial not activated | `{ "error": "Trial not activated", "redeem_url": "https://pokewallet.io/dashboard" }` |
| `403` — trial expired | `{ "error": "Pro plan required", "upgrade_url": "https://pokewallet.io/pricing" }` |

## Images Endpoint

**Authentication Required:** The Images endpoint requires an API key.

GET`/images/:id`

Retrieve card images by card ID with automatic fallback system. Returns binary image data (JPEG, or WebP for localized images). Supports both TCG card IDs (`pk_xxx`) and CardMarket-only card IDs (no prefix). Localized card artwork is available in 5 European languages via the `lang` parameter.

#### Parameters:

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | string | Required | Card ID - Two formats supported:  * **TCG cards:** `pk_xxx` (with prefix) * **CardMarket-only:** hexadecimal hash (no prefix)  Obtained from `/search`, `/cards/:id`, or `/sets/:setCode` |
| `size` | string | Optional | Image size: `low` (~500px, ~50KB) or `high` (~1000px, ~200KB). Default: `low` |
| `lang` | string | Optional | Localized image language: `it`, `fr`, `de`, `es`, or `pt`. If a localized version exists, it is served as WebP; otherwise the request silently falls back to the card's default image (never a 404 because of the language). Check the card's `images.languages` field to know which languages are available. |

#### Response Headers:

* `Content-Type`: `image/jpeg`, or `image/webp` (localized images)
* `X-Image-Lang`: language code of the served image (only present on localized responses, e.g. `it`)
* `Cache-Control`: `public, max-age=31536000, immutable`

#### Localized Images (Multi-Language):

By default, each card is served with its original artwork: **English** for international sets, **Japanese** for Japanese sets. For English-language cards, localized European variants may also be available where a translated print exists: Italian (`it`), French (`fr`), German (`de`), Spanish (`es`) and Portuguese (`pt`).

The recommended flow:

1. Fetch the card from `/cards/:id`, `/search`, or `/sets/:setCode` and read its `images.languages` array (e.g. `["en", "it", "de"]`).
2. If it contains your user's language, request `/images/:id?lang=xx` to get the localized WebP.
3. If it doesn't (or the localized file is missing), the API serves the card's default image (English or Japanese) — requests with `lang` are always safe.

**Backward Compatible:** requests without `lang` behave exactly as before. The `X-Image-Lang` header tells you when a localized WebP was served; its absence means the card's default image (English or Japanese) was returned.

#### Example Requests:

##### TCG Card (with pk\_ prefix):

High Resolution TCG Card

```
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/images/pk_72046138a4c1908a9f27c93fdd8189ba4ac8e683efaed6b9161efcef129302394a9ec1d20d?size=high" \
     --output pikachu_tcg.jpg
```

##### Localized Card Image (Italian):

Localized Card Image

```
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/images/pk_72046138a4c1908a9f27c93fdd8189ba4ac8e683efaed6b9161efcef129302394a9ec1d20d?size=high&lang=it" \
     --output pikachu_it.webp
```

##### CardMarket-Only Card (no prefix):

CardMarket-Only Card Image

```
curl -H "X-API-Key: pk_live_your_key_here" \
     "https://api.pokewallet.io/images/8eb728bd59d4e1a0d94c354e4cc65a7465b55cfa4261bfa93301faa5ec921f97?size=high" \
     --output cubone_v1.jpg
```

**Unique IDs for Variants:** Each CardMarket variant (V1, V2, etc.) has its own unique ID, so you don't need to use a `set` parameter for disambiguation. The ID itself uniquely identifies the exact card variant you want.

#### Example Response (Headers):

```
HTTP/1.1 200 OK
Content-Type: image/jpeg
Content-Length: 123456
Cache-Control: public, max-age=31536000, immutable

[Binary image data]
```

#### Example Response (Localized, Headers):

```
HTTP/1.1 200 OK
Content-Type: image/webp
Content-Length: 98765
X-Image-Lang: it
Cache-Control: public, max-age=31536000, immutable

[Binary image data]
```

## Code Examples

JavaScript Python Node.js Go

JavaScript (Fetch)

```
const API_KEY = process.env.POKEWALLET_API_KEY;
const BASE_URL = 'https://api.pokewallet.io';

async function searchCards(query) {
  const response = await fetch(`${BASE_URL}/search?q=${encodeURIComponent(query)}`, {
    headers: {
      'X-API-Key': API_KEY
    }
  });

  if (!response.ok) {
    if (response.status === 429) {
      throw new Error('Rate limit exceeded');
    }
    throw new Error(`API error: ${response.status}`);
  }

  const data = await response.json();
  return data;
}

async function getCardImage(cardId, size = 'high') {
  const url = `${BASE_URL}/images/${cardId}?size=${size}`;

  const response = await fetch(url, {
    headers: {
      'X-API-Key': API_KEY
    }
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch image: ${response.status}`);
  }

  // Return blob for display or download
  const blob = await response.blob();
  return blob;
}

// Usage - Search TCG cards
searchCards('pikachu')
  .then(data => {
    console.log('TCG card results:', data);
    // IDs will have pk_ prefix
  })
  .catch(error => console.error(error));

// Usage - Search CardMarket-only cards
searchCards('cubone cbb3c')
  .then(data => {
    console.log('CardMarket-only results:', data);
    // IDs will NOT have pk_ prefix
  })
  .catch(error => console.error(error));

// Usage - Get Image (TCG card with pk_ prefix)
getCardImage('pk_72046138a4c1908a9f27c93fdd8189ba...', 'high')
  .then(blob => {
    const imageUrl = URL.createObjectURL(blob);
    document.querySelector('img').src = imageUrl;
  })
  .catch(error => console.error(error));

// Usage - Get Image (CardMarket-only, no prefix)
getCardImage('8eb728bd59d4e1a0d94c354e4cc65a74...', 'high')
  .then(blob => {
    const imageUrl = URL.createObjectURL(blob);
    document.querySelector('img').src = imageUrl;
  })
  .catch(error => console.error(error));
```

Python (Requests)

```
import os
import requests

API_KEY = os.getenv('POKEWALLET_API_KEY')
BASE_URL = 'https://api.pokewallet.io'

def search_cards(query):
    headers = {
        'X-API-Key': API_KEY
    }

    response = requests.get(
        f'{BASE_URL}/search',
        params={'q': query},
        headers=headers
    )

    if response.status_code == 429:
        raise Exception('Rate limit exceeded')

    response.raise_for_status()
    return response.json()

def get_card_image(card_id, size='high', set_code=None):
    headers = {
        'X-API-Key': API_KEY
    }

    params = {'size': size}
    if set_code:
        params['set'] = set_code

    response = requests.get(
        f'{BASE_URL}/images/{card_id}',
        params=params,
        headers=headers
    )

    if response.status_code == 429:
        raise Exception('Rate limit exceeded')

    response.raise_for_status()

    return response.content

# Usage - Search
try:
    data = search_cards('charizard ex')
    print(data)
except Exception as e:
    print(f'Error: {e}')

# Usage - Get Image
try:
    image_data = get_card_image('pk_xxx', size='high', set_code='CBB3C')

    # Save to file
    with open('charizard.jpg', 'wb') as f:
        f.write(image_data)

    print('Image downloaded successfully')
except Exception as e:
    print(f'Error: {e}')
```

Node.js (Axios)

```
const axios = require('axios');
const fs = require('fs');

const API_KEY = process.env.POKEWALLET_API_KEY;
const BASE_URL = 'https://api.pokewallet.io';

async function searchCards(query) {
  try {
    const response = await axios.get(`${BASE_URL}/search`, {
      params: { q: query },
      headers: {
        'X-API-Key': API_KEY
      }
    });

    return response.data;
  } catch (error) {
    if (error.response?.status === 429) {
      throw new Error('Rate limit exceeded');
    }
    throw error;
  }
}

async function getCardImage(cardId, size = 'high', setCode = null) {
  try {
    const params = { size };
    if (setCode) {
      params.set = setCode;
    }

    const response = await axios.get(`${BASE_URL}/images/${cardId}`, {
      params,
      headers: {
        'X-API-Key': API_KEY
      },
      responseType: 'arraybuffer'
    });

    // Get image source
    const imageSource = response.headers['x-image-source'];
    console.log(`Image served from: ${imageSource}`);

    return response.data;
  } catch (error) {
    if (error.response?.status === 429) {
      throw new Error('Rate limit exceeded');
    }
    throw error;
  }
}

// Usage - Search
searchCards('charizard ex')
  .then(data => console.log(data))
  .catch(error => console.error(error));

// Usage - Get Image
getCardImage('pk_xxx', 'high', 'CBB3C')
  .then(imageBuffer => {
    fs.writeFileSync('charizard.jpg', imageBuffer);
    console.log('Image downloaded successfully');
  })
  .catch(error => console.error(error));
```

Go

```
package main

import (
    "encoding/json"
    "fmt"
    "io"
    "net/http"
    "net/url"
    "os"
)

const BaseURL = "https://api.pokewallet.io"

func searchCards(query string) (map[string]interface{}, error) {
    apiKey := os.Getenv("POKEWALLET_API_KEY")

    params := url.Values{}
    params.Add("q", query)

    req, err := http.NewRequest("GET", BaseURL+"/search?"+params.Encode(), nil)
    if err != nil {
        return nil, err
    }

    req.Header.Set("X-API-Key", apiKey)

    client := &http.Client{}
    resp, err := client.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    if resp.StatusCode == 429 {
        return nil, fmt.Errorf("rate limit exceeded")
    }

    body, err := io.ReadAll(resp.Body)
    if err != nil {
        return nil, err
    }

    var result map[string]interface{}
    json.Unmarshal(body, &result)

    return result, nil
}

func getCardImage(cardID, size, setCode string) ([]byte, error) {
    apiKey := os.Getenv("POKEWALLET_API_KEY")

    params := url.Values{}
    params.Add("size", size)
    if setCode != "" {
        params.Add("set", setCode)
    }

    req, err := http.NewRequest("GET", BaseURL+"/images/"+cardID+"?"+params.Encode(), nil)
    if err != nil {
        return nil, err
    }

    req.Header.Set("X-API-Key", apiKey)

    client := &http.Client{}
    resp, err := client.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    if resp.StatusCode == 429 {
        return nil, fmt.Errorf("rate limit exceeded")
    }

    if resp.StatusCode != 200 {
        return nil, fmt.Errorf("failed to fetch image: %d", resp.StatusCode)
    }

    imageData, err := io.ReadAll(resp.Body)
    if err != nil {
        return nil, err
    }

    return imageData, nil
}

func main() {
    // Search example
    data, err := searchCards("charizard ex")
    if err != nil {
        fmt.Println("Error:", err)
        return
    }
    fmt.Println(data)

    // Image example
    imageData, err := getCardImage("pk_xxx", "high", "CBB3C")
    if err != nil {
        fmt.Println("Error:", err)
        return
    }

    // Save to file
    err = os.WriteFile("charizard.jpg", imageData, 0644)
    if err != nil {
        fmt.Println("Error saving image:", err)
        return
    }

    fmt.Println("Image downloaded successfully")
}
```

## Error Handling

The API uses standard HTTP status codes to indicate success or failure:

200

**OK**

Request successful

400

**Bad Request**

Invalid parameters or malformed request

401

**Unauthorized**

Missing or invalid API key

429

**Too Many Requests**

Rate limit exceeded

500

**Internal Server Error**

Something went wrong on our side

### Error Response Format

```
{
  "error": "Error type",
  "message": "Human-readable error description",
  "details": {
    // Additional error information (optional)
  }
}
```

## Best Practices

### Use Environment Variables

Never hardcode API keys. Always use environment variables or secure secret management.

### Handle Rate Limits Gracefully

Implement exponential backoff when you receive a 429 response. Check rate limit headers to avoid hitting limits.

### Cache Results

Cache API responses when appropriate to reduce requests and improve performance.

### Use Search Endpoint

Always use `/search` for the most complete and accurate data.

### Monitor Your Usage

Check your dashboard regularly to track API usage and avoid unexpected rate limit hits.

### Error Handling

Always implement proper error handling for network failures, rate limits, and invalid responses.

**Security Reminder:** Keep your API keys secure. If you suspect a key has been compromised, revoke it immediately from your dashboard and generate a new one.

## Need Help?

If you have questions or run into issues, we're here to help!

[Go to Dashboard](/dashboard)  Contact Support  [Join Discord](https://discord.gg/znDxEjmDVP)

© 2026 PokeWallet. All rights reserved. Built with 💜 by developers, for developers.

**Pokemon TCG API** · **Pokémon TCG API** · **Pokemon API** · **Pokémon API** · **Pokemon Card API** · **TCG API** · **API Pokemon** · **Pokemon Price API** · **Pokemon Card Price API** · **Pokemon Card Database API** · **Pokemon TCG Pocket API** · **Real-time Card Prices** · **Collection Tracker** · **REST Pokemon API** · **TCG Wallet API** · **Pokemon Trading Card Game Developer Platform** · **TCG Collection Management API** · **Pokemon Card Market Data API** · **Pokemon TCG REST API** · **Pokemon Card Collection Tracker** · **TCG Portfolio Management** · **Best Pokemon Card API 2025** · **Free Pokemon TCG API** · **Pokemon Card Price Tracker API** · **Pokemon TCG Developer Tools** · **tcgdex Alternative** · **tcgdex API Rate Limit Alternative** · **pokemontcg.io Alternative** · **scrydex Alternative** · **PokemonPriceTracker Alternative** · **Pokemon Price Tracker API Alternative** · **PriceCharting Pokemon API Alternative** · **PriceCharting API Pokemon Cards** · **Pokemon TCG API Documentation** · **Full Pokemon API Documentation** · **PokeAPI TCG Alternative** · **justtcg API Alternative** · **apitcg Alternative** · **Fastest Pokemon API** · **Pokemon API Comparison** · **Better than tcgdex** · **Better than pokemontcg.io** · **Better than PokemonPriceTracker** · **Pokemon Collection API for Developers** · **Build Pokemon Card App** · **Pokemon Portfolio Tracker API** · **Pokemon Card Value Calculator API**

**One Piece Card Game API** · **OPCG API** · **One Piece TCG API** · **One Piece Card Price API** · **OP Card API** · **One Piece Card Database API** · **OPCG Price Tracker API** · **One Piece Card Game Developer API** · **One Piece Card Game REST API** · **OP01 API** · **OP07 API** · **One Piece TCG Card Prices** · **One Piece Card Game Collection Tracker API** · **Build One Piece Card App**

© 2026 PokeWallet is not affiliated with, endorsed by, or connected to Nintendo, Creatures Inc., Game Freak, or The Pokémon Company. All Pokémon characters, names, and related indicia are © Nintendo, Creatures Inc., Game Freak, The Pokémon Company. This platform provides data aggregation and API services for informational purposes only.

**[Blog](/blog)[API Docs](/api-docs)[One Piece API](/berrywallet)[Terms and Conditions](/terms-conditions)[Privacy Policy](/privacy-policy)**