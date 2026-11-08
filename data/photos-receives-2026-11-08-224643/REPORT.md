# Japanese sealed booster boxes — FINN.no report

Date: 2026-11-08. Companion to [`offer.md`](offer.md) (the ¥ offer) and [`offer.json`](offer.json).

## 1. Status

Thirteen FINN searches, run one at a time, one page each, restricted to the
verified card category (`category=0.86`, `sub_category=1.86.285`,
`product_category=2.86.285.396`).

| # | Query | Ads | `match_count` | Pages | Run |
|---|---|---|---|---|---|
| 1 | `pokemon booster box` | 53 | 1 522 | 29 | `2026-11-08-221957` |
| 2 | `pokemon booster box japansk` | 53 | 267 | 6 | `2026-11-08-222012` |
| 3 | `japanske pokemon kort` | 53 | 4 502 | 50 | `2026-11-08-222024` |
| 4 | `pokemon display box` | 53 | 306 | 6 | `2026-11-08-222035` |
| 5 | `pokemon sealed` | 53 | 2 849 | 50 | `2026-11-08-222047` |
| 6 | `pokemon booster box sealed` | 53 | 951 | 18 | `2026-11-08-222506` |
| 7 | `pokemon japansk booster` | 53 | 492 | 10 | `2026-11-08-222517` |
| 8 | `pokemon booster boks` | 53 | 706 | 14 | `2026-11-08-222527` |
| 9 | `pokemon eevee heroes` | 53 | 367 | 7 | `2026-11-08-222537` |
| 10 | `pokemon vstar universe` | 53 | 186 | 4 | `2026-11-08-222548` |
| 11 | `pokemon lost abyss` | 15 | 15 | 1 | `2026-11-08-222559` |
| 12 | `pokemon 25th anniversary` | 53 | 265 | 5 | `2026-11-08-222609` |
| 13 | `pokemon 151 booster box` | 53 | 317 | 6 | `2026-11-08-222621` |

**483 unique ads** after dedupe by FINN-kode. No ad pages were scraped — this is
search-result data only.

## 2. What the searches found

### 2.1 Japanese sealed booster boxes (31 ads)

| FINN-kode | NOK | Heading |
|---|---|---|
| 472039650 | 799 | Abyss Eye Booster Box Japansk |
| 480373254 | 900 | Stellar Miracle Booster Box - japansk! |
| 480396681 | 950 | Pokémon Mega Symphonia Japansk Boosterboks |
| 480396500 | 950 | Pokémon Mega Brave Japansk Boosterboks |
| 480395875 | 950 | Pokémon Storm Emeralda Japansk Boosterboks |
| 480587151 | 990 | Japansk Nihil Zero Booster Box |
| 480227708 | 990 | Japansk Nihil Zero Booster Box |
| 480378085 | 1 099 | Pokémon Mega Dream ex – Japansk Booster Box |
| 480193149 | 1 100 | Crimson Haze Booster Box Sealed Japansk Pokemon |
| 479076284 | 1 149 | Pokémon Incandescent Arcana Booster Box Japansk |
| 480082813 | 1 250 | Pokémon Heat Wave Arena japansk boosterboks |
| 480587161 | 1 299 | Japansk Mega Dream ex - Booster Box |
| 480587145 | 1 299 | Japansk Mega Symphonia - Booster Box |
| 480394719 | 1 299 | Pokemon Inferno X booster box Japansk |
| 480227709 | 1 299 | Japansk Mega Symphonia - Booster Box |
| 480227702 | 1 299 | Japansk Mega Dream ex - Booster Box |
| 480380062 | 1 499 | Pokémon Inferno X – Japansk Booster Box |
| 463817842 | 1 750 | Super Electric Breaker Japansk Booster Display Box |
| 476606430 | 1 899 | Pokemon 30th Celebration Japansk Display Booster Box |
| 480587158 | 2 099 | Japansk Terastal Festival ex Booster Box |
| 479077088 | 2 099 | Pokémon Shiny Star V Booster Box Japansk |
| 480227703 | 2 099 | Japansk Terastal Festival ex Booster Box |
| 479075557 | 2 399 | Pokémon GO Booster Box Japansk |
| 477280195 | 2 500 | Pokémon 30th Celebration Booster Box japansk |
| 478648073 | 2 599 | Pokémon 30th Celebration Booster Box Japansk |
| 480092769 | 3 200 | Pokémon Scarlet & Violet 151 Japansk Booster Box |
| 480411707 | 3 500 | Pokémon Card 151 – Japansk Booster Box |
| 479354763 | 3 500 | 🇯🇵 ❤️ Pokémon 151 – Japansk Booster Box ❤️ 🇯🇵 |
| 470097965 | 4 290 | Pokemon Lost Abyss japansk boosterboks |
| 480254788 | 4 930 | Pokémon Japansk VMAX Climax Booster box sealed boks high class 2021 |
| 479522079 | 37 500 | Stor sealed japanske boosterbokser |

Four more are Japanese by set name with the language unstated:
`480197835` Shiny Treasure ex SV4a (1 395), `480424068` Shiny Treasure ex (1 700),
`474042449` Mega Dream sealed (1 540), `467898771` Lost Abyss (3 999).

### 2.2 Price level

- Single Japanese boxes: **799 – 4 930 NOK**, median **2 099 NOK**.
- One bulk lot: **37 500 NOK** (`479522079`).
- The offer averages **958 NOK/box** (3 333 065 NOK ÷ 3 480 boxes).

### 2.3 Three traps in the data

1. **Naming.** The offer's *Munikis Zero* is FINN's *Nihil Zero*; *Storm Emerald*
   is *Storm Emeralda*. A matcher without these aliases misses the comparables.
2. **False positives.** Three ads in the Japanese bucket are not booster boxes:
   `478215833` is a single **booster pack** (799), `480361020` and `480361125`
   are **25th Anniversary Golden Boxes** (4 550 / 15 999). Excluded above.
3. **Not Japanese.** `479755949` "151C Gathering" (790) is Chinese, and
   `480586824` "30th Celebration (Kinesisk)" is Chinese. Cheap, but not comparable.

## 3. Offer vs FINN asking price

FINN's *lowest* asking price per set, against the offer's per-box NOK.

| Set | Offer NOK/box | FINN lowest ask | FINN ÷ offer |
|---|---|---|---|
| Pokémon Card 151 | 3 123 | 3 200 | 1.02× |
| Heat Wave Arena | 1 194 | 1 250 | 1.05× |
| Stellar Miracle | 800 | 900 | 1.13× |
| Inferno X | 1 105 | 1 299 | 1.18× |
| Shiny Treasure ex | 1 164 | 1 395 | 1.20× |
| Lost Abyss | 3 224 | 3 999 | 1.24× |
| 30th CELEBRATION | 1 523 | 1 899 | 1.25× |
| Mega Dream ex | 776 | 1 099 | 1.42× |
| Abyss Eye | 537 | 799 | 1.49× |
| Storm Emerald | 579 | 950 | 1.64× |
| Terastal Festival ex | 1 206 | 2 099 | 1.74× |
| Mega Brave | 520 | 950 | 1.83× |
| Munikis Zero / Nihil Zero | 537 | 990 | 1.84× |
| Mega Symphonia | 508 | 950 | 1.87× |
| VMAX Climax | 1 911 | 4 930 | 2.58× |

**Median: FINN asks ≈ 1.42× the offer price.** On the whole-lot average,
2 099 ÷ 958 ≈ **2.2×**.

### 3.1 The 22 sets with no comparable

Snow Hazard, Violet ex, VSTAR Universe, Paradigm Trigger, Battle Region,
25th Anniversary Collection, Eevee Heroes, Jet-Black Spirit, Silver Lance,
30th CELEBRATION 9-Item Set, Ninja Spinner, Black Bolt, White Flare,
the unnamed ¥25 800 line, Battle Partners, Night Wanderer, Mask of Change,
Ancient Roar, Future Flash, Ruler of the Black Flame, Raging Surf, Clay Burst.

This matters: the three most expensive sets in the offer — **Eevee Heroes
(7 763 NOK/box), 25th Anniversary Collection (3 822), VSTAR Universe (1 744)** —
have **no** box comparable on FINN. Eevee Heroes appears only as a single pack
at 799; VSTAR Universe only as singles at 20–1 899. Those are exactly the sets
where a wrong price costs the most, and FINN cannot validate them.

## 4. Is any of this even worth it?

My honest read: **the searches were worth it, the scraping mostly is not.**

### What the searches already settled

- The offer is priced at **wholesale**, not at a scam level. A consistent
  1.0–2.6× retail markup across 15 independent sets is what a real distributor
  price looks like. That is a useful, cheap conclusion.
- The offer is **not a bargain**. Nothing here is mispriced in your favour.

### Why the margin is not what it looks like

- **FINN prices are asking prices, not sold prices.** The 1.42× is a retail
  markup, not profit. It has to cover FINN fees, shipping, VAT and months of
  your time.
- **Liquidity is the real constraint, not price.** The offer is 50–500 boxes per
  set — 3 480 boxes total. FINN's *entire* Japanese sealed supply is 31 listings,
  almost all single boxes. Selling 3 480 boxes at the median ask would gross
  ≈ 7.3M NOK against a 3.33M NOK cost, but the market cannot absorb that volume.
  You would realistically move a few dozen.
- **22 of 37 sets are unvalidated**, including the three most valuable ones.

### Verdict on scraping

| Target | Worth it? | Why |
|---|---|---|
| `479522079` — 37 500 NOK bulk lot | **Yes, first** | The only wholesale-scale listing. Its description may reveal a real per-box wholesale price achieved in Norway — the one number that could change the conclusion. |
| The 31 single-box ads | **Yes, but low value** | Gives a properly sourced per-set table instead of "lowest ask". ~31 requests. Will not change the 1.42× picture. |
| The `480586xxx`/`480587xxx` cluster | **Marginal** | ~18 ads from one reseller. Useful as a price list, but it is one seller's opinion, not a market. |
| Singles, ETBs, English/Korean/Chinese boxes | **No** | Different product. The price is the acrylic case or the language, not the box. |

**Bottom line:** scrape the bulk lot, and the 31 boxes if you want a clean table.
Do not expect scraping to turn this into a good deal — it will confirm the
wholesale reading, not overturn it. The decision this data supports is about
whether you want to run a retail operation on 3 480 boxes, not about whether the
¥ prices are fair.

## 5. Files

| File | What |
|---|---|
| [`offer.md`](offer.md) | The ¥ offer, with NOK and totals |
| [`offer.json`](offer.json) | Same, machine-readable |
| [`build_offer_md.py`](build_offer_md.py) | Regenerates `offer.md` from `offer.json` |
| [`probe_price_sources.py`](probe_price_sources.py) | One-request probe of 7 external price sources |
| [`analyze_finn_sealed.py`](analyze_finn_sealed.py) | Aggregates the 13 FINN runs into the buckets above |
| `data/finn/searches/2026-11-08-22*/` | Raw HTML + `all_ads.jsonl` for all 13 runs |
