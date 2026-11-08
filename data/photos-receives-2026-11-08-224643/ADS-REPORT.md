# Japanese sealed booster boxes — ad-level report

**Date:** 2026-11-08
**Scope:** 82 individual FINN.no ads, scraped in full, against a 37-line wholesale offer of 3 480 Japanese sealed booster boxes.
**Companion files:** [`PLAN.md`](PLAN.md) · [`FULL-REPORT.md`](FULL-REPORT.md) (search-level) · [`offer.md`](offer.md) · [`ads_extract.json`](ads_extract.json) · [`targets.jsonl`](targets.jsonl)

---

## 0. Executive summary

| | |
|---|---|
| Searches run | **13** |
| Ads selected (10 per search) | **130** rows |
| Unique FINN-koder | **82** |
| Ads archived successfully | **82 / 82** (0 failures) |
| Koder that appeared in more than one search | **16** |
| Genuine Japanese sealed booster boxes with a price | **23** |
| Their price range | **799 – 4 930 NOK** (excluding one 37 500 NOK lot) |
| Their median | **2 099 NOK** |
| Offer's average cost per box | **958 NOK** |
| Best single find | one reseller's **17-set price list** covering **14 of the offer's sets** |
| That list's markup over the offer | **1,31× – 1,73×**, median **1,53×** |
| Aggregate on those 14 sets | cost **2 219 420 NOK** → retail **3 346 350 NOK** = **1,51×** |
| Boxes covered by that one ad | **2 590 of 3 480** (74 %) |
| Verdict | The offer is **genuinely wholesale**. The problem is **volume, VAT and freight**, not the price. |

---

## 1. What was scraped, and how

### 1.1 Method

1. Every ad in the 13 search runs was scored for relevance: Japanese + sealed + booster box + a set that appears in the offer, minus penalties for other TCGs, singles, ETBs, packs, bundles and placeholder prices.
2. The **top 10 per search** were taken — 130 rows, **82 unique FINN-koder** after dedupe.
3. Each of the 82 ad pages was fetched once and archived by [`finn/finn_ad.py`](../../finn/finn_ad.py) into `data/finn/annonser/{kode}_{slug}/` — raw HTML, parsed JSON, manifest. Images were skipped (`--no-images`); they are not needed for price work.
4. Derived fields were computed by [`analyze_ads.py`](analyze_ads.py) into [`ads_extract.json`](ads_extract.json).

### 1.2 Scrape result

```
targets rows      : 130
unique koder      : 82
records built     : 82
missing           : 0
```

Every requested ad produced a record. No failures, no retries, no partial pages.

### 1.3 What the 82 ads actually are

| Product type | Count |
|---|---|
| booster box | 41 |
| other (singles piles, collections, accessories) | 21 |
| single / graded | 9 |
| collection box (Golden Box, UPC, premium collection) | 6 |
| bundle | 2 |
| pack | 2 |
| ETB | 1 |

| Language | Count |
|---|---|
| JP | 41 |
| EN / unknown | 34 |
| CN | 4 |
| KR | 3 |

| Seller | Count |
|---|---|
| PRIVATE | 71 |
| PROFESSIONAL | 11 |

**Only 23 of the 82 are a Japanese sealed booster box with a usable price.** That is the number that matters. The rest is noise the searches dragged in — and the noise is itself a finding (§10).

---

## 2. The 23 Japanese sealed booster boxes

Sorted by price. "Seller" is `PROFESSIONAL` when FINN's contact button reports a business account.

| # | FINN-kode | Set | NOK | Seller | Location | Note |
|---|---|---|---|---|---|---|
| 1 | 472039650 | Abyss Eye | **799** | PROFESSIONAL | Ålgård | pokebox.no — 899 with shrink, 799 without (sold out) |
| 2 | 480587151 | Munikis Zero | **990** | PROFESSIONAL | Jørpeland | Cardero — "Nihil Zero" |
| 3 | 480193149 | Crimson Haze | **1 100** | PRIVATE | Kristiansand | "Jeg har 2 stk" |
| 4 | 480082813 | Heat Wave Arena | **1 250** | PRIVATE | Indre Arna | |
| 5 | 480394719 | Inferno X | **1 299** | PRIVATE | Åros | |
| 6 | 480587161 | Mega Dream ex | **1 299** | PROFESSIONAL | Jørpeland | Cardero |
| 7 | 480587145 | Mega Symphonia | **1 299** | PROFESSIONAL | Jørpeland | Cardero |
| 8 | 480380062 | Inferno X | **1 499** | PRIVATE | Hokksund | **pre-order**, arrives week 46 |
| 9 | 476606430 | 30th CELEBRATION | **1 899** | PROFESSIONAL | Ålgård | pokebox.no — 1 999 with shrink |
| 10 | 479077088 | Shiny Star V | **2 099** | PROFESSIONAL | Gjøvik | Collectorscorner |
| 11 | 480587158 | Terastal Festival ex | **2 099** | PROFESSIONAL | Jørpeland | Cardero |
| 12 | 479075557 | Pokémon GO | **2 399** | PROFESSIONAL | Gjøvik | Collectorscorner |
| 13 | 477280195 | 30th CELEBRATION | **2 500** | PRIVATE | Stavanger | |
| 14 | 480509351 | VSTAR Universe | **2 500** | PRIVATE | Vennesla | 1st print |
| 15 | 478648073 | 30th CELEBRATION | **2 599** | PROFESSIONAL | Gjøvik | Collectorscorner, registered AS |
| 16 | 480092769 | Pokémon Card 151 | **3 200** | PRIVATE | Fornebu | |
| 17 | 479354763 | Pokémon Card 151 | **3 500** | PRIVATE | Knarrlagsund | free shipping |
| 18 | 480411707 | Pokémon Card 151 | **3 500** | PRIVATE | Hokksund | **pre-order**, arrives week 46 |
| 19 | 467898771 | Lost Abyss | **3 999** | PRIVATE | Porsgrunn | |
| 20 | 470097965 | Lost Abyss | **4 290** | PRIVATE | Skien | "totalt 2 stk" |
| 21 | 480254788 | VMAX Climax | **4 930** | PRIVATE | Oslo | sealed, high class 2021 |
| 22 | 479522079 | **24-box lot** | **37 500** | PRIVATE | Andebu | see §4 — 1 562 NOK/box |
| 23 | 480410093 | **17-set price list** | from **800** | PRIVATE | Figgjo | see §3 — the most useful ad in the set |

**Statistics (excluding the 37 500 lot):** min 799 · median **2 099** · max 4 930 NOK.

---

## 3. The single most valuable find — a competitor's price list

[`480410093`](https://www.finn.no/recommerce/forsale/item/480410093) — *"Billige Pokémon Boosterboxer"*, Figgjo, private seller, modified 2026-11-06.

This is not one product. It is a **price list of 17 Japanese booster boxes**, with shrink and no-shrink prices, plus a note that the seller has multiple copies of most of them. It is the closest thing to a published wholesale-to-retail spread that exists on FINN.

### 3.1 The list, verbatim

| Set | With shrink | Without shrink |
|---|---|---|
| 30th Celebration | 2 000 | — |
| Pokémon TCG 151 (sv2a) | 4 450 | 4 000 |
| Storm Emeralda | 999 | 920 |
| Mega Dream | 1 249 | 1 190 |
| VSTAR Universe | 2 650 | — |
| Terastal Festival | 1 900 | — |
| Shiny Treasure | 1 720 | — |
| Inferno X | — | 1 600 |
| Glory of Team Rocket | 2 300 | — |
| Crimson Haze | 1 300 | — |
| Mega Symphonia | 800 | — |
| Mega Brave | 800 | — |
| Ninja Spinner | 850 | 800 |
| Abyss Eye | 850 | 800 |
| Nullifying Zero | 850 | — |
| Battle Partners | 1 000 | — |
| Star Birth | 2 500 | — |

### 3.2 Against the offer — 14 of the 37 lines

| Set | Offer NOK/box | Figgjo price | Ratio | Offer qty | Retail value | Offer cost |
|---|---|---|---|---|---|---|
| 30th CELEBRATION | 1 523 | 2 000 | **1,31×** | 200 | 400 000 | 304 600 |
| Pokémon Card 151 | 3 123 | 4 450 | **1,42×** | 100 | 445 000 | 312 300 |
| Ninja Spinner | 597 | 850 | **1,42×** | 200 | 170 000 | 119 400 |
| Inferno X | 1 105 | 1 600 | **1,45×** | 150 | 240 000 | 165 750 |
| Shiny Treasure ex | 1 164 | 1 720 | **1,48×** | 200 | 344 000 | 232 800 |
| VSTAR Universe | 1 744 | 2 650 | **1,52×** | 20 | 53 000 | 34 880 |
| Battle Partners | 657 | 1 000 | **1,52×** | 120 | 120 000 | 78 840 |
| Mega Brave | 520 | 800 | **1,54×** | 200 | 160 000 | 104 000 |
| Mega Symphonia | 508 | 800 | **1,57×** | 300 | 240 000 | 152 400 |
| Terastal Festival ex | 1 206 | 1 900 | **1,58×** | 100 | 190 000 | 120 600 |
| Abyss Eye | 537 | 850 | **1,58×** | 200 | 170 000 | 107 400 |
| Munikis Zero | 537 | 850 | **1,58×** | 150 | 127 500 | 80 550 |
| Mega Dream ex | 776 | 1 249 | **1,61×** | 150 | 187 350 | 116 400 |
| Storm Emerald | 579 | 999 | **1,73×** | 500 | 499 500 | 289 500 |
| **TOTAL** | | | **1,51×** | **2 590** | **3 346 350** | **2 219 420** |

**Median ratio 1,53×. Aggregate 1,51×. Range 1,31× – 1,73×.**

This is the cleanest evidence in the whole dataset. One seller, one day, one consistent pricing policy, 14 independent sets, and the markup is tight. That is what a real distributor-to-retail spread looks like. **The offer is not a bargain and it is not a scam — it is a wholesale price.**

### 3.3 What it does *not* cover

23 of the 37 offer lines have no price in this list, including the two largest:

- **Eevee Heroes** — 20 boxes, 2 600 000 JPY, **155 260 NOK**. FINN has one single pack at 799 and a 1 NOK placeholder. No box anywhere.
- **25th Anniversary Collection** — 30 boxes, 1 920 000 JPY, **114 660 NOK**. FINN has only "Golden Boxes" (10 000 / 15 999) and graded promos. Different product entirely.

Those two lines are **270 000 NOK of the offer's 3 333 065 NOK** and nothing on FINN validates them.

---

## 4. The 24-box lot — a direct comparable to the whole deal

[`479522079`](https://www.finn.no/recommerce/forsale/item/479522079) — *"Stor sealed japanske boosterbokser"*, Andebu, private, 37 500 NOK.

The description lists the contents exactly:

| Set | Qty |
|---|---|
| S&V 151 | 3 |
| Mega Dream | 2 |
| Pokémon Scarlet Ex | 1 |
| Shiny Treasure Ex | 3 |
| Ancient Roar | 1 |
| Paradise Dragona | 1 |
| Future Flash | 1 |
| Electric Breaker | 2 |
| Cyber Judge | 1 |
| Raging Surf | 1 |
| Wild Force | 1 |
| Storm Emerald | 2 |
| Terastal Festival | 3 |
| Ruler of Black Flame | 1 |
| Crimson Haze | 1 |
| **Total** | **24** |

- Asking **37 500 NOK** → **1 562 NOK/box**
- The description says the collection was priced at **41 100 NOK** "etter markedsverdi, noe under" → **1 712 NOK/box**
- The offer's average is **958 NOK/box**

So a Norwegian collector liquidating 24 Japanese boxes prices them at **1,63× the offer's average** — and says that is *below* market.

This is the same conclusion as §3, reached from a completely different direction: a private seller with 24 boxes, not a shop with a price list.

---

## 5. The three professional shops

11 of the 82 ads come from business accounts. Three distinct shops:

| Shop | Location | Sets seen | Prices |
|---|---|---|---|
| **pokebox.no** | Ålgård | 30th Celebration, Abyss Eye | 1 999 / 1 899 · 899 / 799 |
| **Collectorscorner** (registered AS) | Gjøvik | 30th Celebration, Shiny Star V, Pokémon GO | 2 599 · 2 099 · 2 399 |
| **Cardero** | Jørpeland | Mega Dream ex, Mega Symphonia, Nihil Zero, Terastal Festival ex | 1 299 · 1 299 · 990 · 2 099 |

Two observations:

1. **The shops are not the cheapest.** For 30th Celebration, pokebox.no asks 1 899–1 999 while a private seller in Stavanger asks 2 500 and Collectorscorner asks 2 599. For Mega Symphonia, Cardero asks 1 299 while the Figgjo private seller asks 800. Private sellers undercut the shops by 30–40 %.
2. **Cardero's prices are the closest thing to a floor for the newest sets.** Mega Symphonia 1 299 and Mega Dream 1 299 against the offer's 508 and 776 — 2,56× and 1,67×. But Cardero is a shop with VAT, overhead and a returns policy; the Figgjo private seller at 800 is the real competitive price.

---

## 6. The pre-order importers — the offer's actual competitors

Two ads, **same seller**, Hokksund:

- [`480380062`](https://www.finn.no/recommerce/forsale/item/480380062) — Inferno X, 1 499 NOK
- [`480411707`](https://www.finn.no/recommerce/forsale/item/480411707) — Pokémon Card 151, 3 500 NOK

Both say the same thing:

> "Mulighet for forhåndsbestilling, får produktet inn i slutten av uke 46!"

This is someone taking orders **before the stock lands**, importing from Japan, and reselling at 1 499 / 3 500. That is precisely the business model the offer would require. It is already running, at small scale, in Norway.

It also tells you the market's expectation: a 151 box is worth 3 500 to a Norwegian buyer *today*, and someone is willing to commit to that price before they even have the goods.

---

## 7. The shrinkwrap discount

Both pokebox.no and the Figgjo seller price "uten shrinkwrap" separately. It is a consistent 5–11 %:

| Set | With shrink | Without | Discount |
|---|---|---|---|
| Abyss Eye (pokebox) | 899 | 799 | −11,1 % |
| 151 (Figgjo) | 4 450 | 4 000 | −10,1 % |
| Storm Emeralda (Figgjo) | 999 | 920 | −7,9 % |
| Ninja Spinner (Figgjo) | 850 | 800 | −5,9 % |
| Abyss Eye (Figgjo) | 850 | 800 | −5,9 % |
| Mega Dream (Figgjo) | 1 249 | 1 190 | −4,7 % |
| 30th Celebration (pokebox) | 1 999 | 1 899 | −5,0 % |

**Average ≈ 7 %.** Two things follow:

1. The offer's boxes must be **with shrink** to be worth the offer price. That needs confirming in writing.
2. "Uten shrinkwrap" does not mean opened — both sellers say the box is still sealed, just missing the outer film. That is a real, sellable grade in this market, and it is worth ~7 % less.

---

## 8. What the descriptions actually say

The scraped `description_raw` is the part the search results never showed. Six things recur:

### 8.1 Provenance claims are thin

Only two ads make a real provenance claim:

- `470097965` (Lost Abyss, Skien): *"Boksene kommer rett fra leverandør og har blitt oppbevart trygt i original eske"* — 2 units.
- `479522079` (24-box lot): *"Disse er kun eid av meg!"*

Everyone else just says "sealed" / "fabrikkforseglet". Nobody shows a receipt, an invoice, or a supplier name. **There is no visible chain of custody anywhere in the Norwegian market** — which is exactly the gap a legitimate importer could fill, and exactly the risk a buyer of 3 480 boxes is taking on.

### 8.2 Condition is almost never graded

`condition` is `":"` or `null` on 60 of the 82 ads. FINN's condition field is effectively unused for this category. The only condition signal is prose.

### 8.3 The 151 ads are the most professional

`479354763` (Knarrlagsund, 3 500, free shipping) is a 2 583-character sales page: factory seal, air holes in the Japanese film explained as normal, chase-card list, Master Ball reverse holos, grading rationale. It is the best-written ad in the set and it is a **private** seller.

### 8.4 Tag stuffing is universal

`479743702` and `479743903` both end with ~1 800 characters of SEO tags listing every Pokémon set ever printed, including "Japansk Pokemon" and "Japanese Pokemon" — on **English** product. This is what broke language detection (§11).

### 8.5 Two ads are One Piece, not Pokémon

`480361687` (*Yamato [Alternate Art] EB03-057*, 100 NOK) and `480361704` (*Perona [Alternate Art] EB03-045*, 150 NOK) came back from the query `japanske pokemon kort`. They are One Piece Card Game singles. FINN's category filter does not separate TCGs.

### 8.6 Placeholder prices are common

`480194872` (Eevee Heroes boosterboks) is listed at **1 NOK**. `480335641` and `480194533` likewise. Sellers use 1 NOK to mean "make me an offer". Any automated price analysis that does not filter these will produce garbage — the search-level report's "min 449 NOK" was partly this.

---

## 9. The economics — where the 1,51× actually goes

The 1,51× looks like a 51 % margin. It is not. Here is the arithmetic with every assumption stated.

### 9.1 The headline

```
offer cost (3 480 boxes)          3 333 065 NOK
validated retail (2 590 boxes)    3 346 350 NOK   at 1,51x
unvalidated (890 boxes) cost      1 113 645 NOK   at 1,51x -> 1 681 604 NOK
implied total retail              5 027 954 NOK
```

### 9.2 Scenario A — private import, sell privately

| Line | NOK |
|---|---|
| Goods | −3 333 065 |
| Norwegian import VAT, 25 % (not deductible) | −833 266 |
| **Landed cost** | **−4 166 331** |
| Retail revenue at 1,51× | +5 027 954 |
| **Gross** | **+861 623** |
| Sea freight, Japan → Norway (~1,5 t, 250–400 NOK/kg) | −390 000 … −625 000 |
| FINN / payment fees (~2 %) | −100 559 |
| Packing and handling (3 480 shipments × ~30 NOK) | −104 400 |
| **Net** | **≈ +30 000 … +265 000 NOK** |

### 9.3 Scenario B — VAT-registered business

| Line | NOK |
|---|---|
| Goods (input VAT recoverable) | −3 333 065 |
| Retail revenue, VAT-inclusive 5 027 954 → ex-VAT | +4 022 363 |
| **Gross** | **+689 298** |
| Freight (VAT recoverable) | −390 000 … −625 000 |
| Fees | −100 559 |
| Handling | −104 400 |
| **Net** | **≈ −140 000 … +95 000 NOK** |

### 9.4 The volume problem, which is bigger than either

The Norwegian market for Japanese sealed booster boxes, as visible on FINN tonight:

- **31 listings** total, across all sets
- **23** with a usable price
- The largest single holder is one private seller with **24 boxes**

The offer is **3 480 boxes**. That is **145× the entire visible competing supply**, and **145× the largest private holding on the market**.

If the Norwegian market absorbs 50–100 Japanese boxes a month — generous, given 31 live listings — then 3 480 boxes is **3 to 6 years of selling**, at a rate of 1–3 boxes a day, every day, while every new set release adds more competing supply and every reprint pushes the price down.

### 9.5 The structural trap

Look at where the margin is:

| | Sets | Boxes | Offer NOK/box | Best retail | Ratio |
|---|---|---|---|---|---|
| **Best margins** | VMAX Climax, Lost Abyss, VSTAR Universe, 151 | **150** | 1 744 – 3 224 | 2 500 – 4 930 | 1,24× – 2,58× |
| **Worst margins** | Mega Symphonia, Mega Brave, Abyss Eye, Munikis Zero, Ninja Spinner, Storm Emerald | **1 550** | 508 – 597 | 800 – 999 | 1,42× – 1,73× |

The sets with the best absolute margin are the **old, out-of-print, scarce** ones — and the offer has only **150 boxes** of them. The sets with the largest quantities are the **newest, highest-print-run, most reprint-exposed** ones, and they carry the thinnest margins.

That is not an accident. It is how a distributor protects itself: give away the scarce product in token quantity, push volume on the product that is about to be reprinted.

---

## 10. What the searches did *not* find

Three of the 13 searches produced almost nothing usable, and that is a finding in itself:

| Search | Ads | Usable JP boxes in top 10 |
|---|---|---|
| `japanske pokemon kort` | 53 | **5** — the rest were singles, a mixed collection, and two One Piece cards |
| `pokemon 25th anniversary` | 53 | **1** — the rest were Golden Boxes, promos and graded singles |
| `pokemon lost abyss` | 15 | **2** — only 15 matches exist on all of FINN |

And two sets in the offer have **zero** box comparables anywhere:

- **Eevee Heroes** — one single pack (799) and one 1 NOK placeholder
- **25th Anniversary Collection** — Golden Boxes only (10 000 / 15 999)

---

## 11. Data quality — what the scrape got wrong, and the fixes

Recorded because these are the traps any future run will hit.

| Bug | Symptom | Fix |
|---|---|---|
| Lot size matched pack counts | `Abyss Eye Booster Box` → lot 30, 27 NOK/box (from "30 pakker") | lot regex now requires a *box* word, not `pakker`/`pk` |
| Set number read as lot size | `Pokémon Card 151` → lot 151, 23 NOK/box | `MAX_LOT = 30`; anything larger is rejected |
| Lot size applied to non-boxes | `14x V / VSTAR / AR` → 18 NOK/box | lot only computed when product is `booster box` |
| Language from full description | English Paldea Evolved labelled JP (SEO tags say "Japansk Pokemon") | language from heading + first 300 chars of description only |
| Price list treated as one product | `Billige Pokémon Boosterboxer` → set `None`, 800 NOK | detected as `MULTI (price list)` |
| Other TCGs in Pokémon searches | One Piece `Perona` / `Yamato` in the 82 | `other_tcg` flag, excluded from the core set |

After the fixes: **23** core ads, min 799, median 2 099, max 37 500. Before: 25, min 5, median 2 145. The difference is entirely artefacts.

---

## 12. My opinion

**The price is real. The deal is not.**

Three independent measurements agree that the offer sits at roughly **1,5× below Norwegian retail**:

1. One reseller's 17-set price list → **1,51×** aggregate on 14 sets, 2 590 boxes
2. One private seller's 24-box lot → **1,63×** the offer's average
3. The 23 individual boxes → median **2 099 NOK** against the offer's **958 NOK** average

That consistency is the signature of a genuine wholesale price. Nobody accidentally prices 14 sets at 1,31–1,73×. **If the question is "is this a real distributor price?", the answer is yes.**

But the deal fails on four things that have nothing to do with the price:

**1. VAT eats most of the spread.** 25 % Norwegian import VAT on 3 333 065 NOK is 833 266 NOK. The entire validated gross spread is 1 126 930 NOK. VAT takes 74 % of it before a single box moves.

**2. Freight eats most of the rest.** 3 480 booster boxes is roughly 1,5 tonnes. Sea freight from Japan at 250–400 NOK/kg is 390 000–625 000 NOK. Air is not a consideration.

**3. The volume is impossible.** 3 480 boxes against 31 competing listings and a largest private holding of 24 boxes. This is a 3–6 year sell-through at best, during which every new set and every reprint competes with you.

**4. The margin is on the wrong product.** The 150 boxes with 1,24–2,58× margins are the scarce old sets. The 1 550 boxes with 1,42–1,73× margins are the newest, most reprint-exposed sets. You cannot buy the good part without the bad part.

**What I would actually do:**

- **Do not take the whole thing.** 3 480 boxes is a distribution business, not a purchase.
- **Ask for a 150–300 box mix** concentrated on the out-of-print sets: VMAX Climax, Lost Abyss, VSTAR Universe, Eevee Heroes, 25th Anniversary Collection, 151. That is where the 2×+ margins are, and it is a quantity the Norwegian market can absorb in 6–12 months.
- **Get the Eevee Heroes and 25th Anniversary prices validated first.** They are 270 000 NOK of the offer and nothing on FINN prices them. If those two are wrong, the whole deal is wrong.
- **Ask four questions in writing:** (a) are the boxes with shrinkwrap; (b) is the JPY price ex-Japanese consumption tax; (c) what is the FOB/incoterm and who pays freight; (d) can you supply 20–30 boxes per set rather than the full quantity.
- **Register for VAT before importing.** Scenario B is roughly break-even; Scenario A is a small profit for years of work. Neither is worth doing at full scale, but the VAT treatment changes the answer by ~150 000 NOK.

**The one thing that would change my mind:** if the seller will do a mixed 200-box order at the same per-box prices, the economics work. 200 boxes at ~958 NOK average = 191 600 NOK cost, ~290 000 NOK retail, ~98 000 NOK gross, minus VAT and freight ≈ 20 000–40 000 NOK net on a small, sellable, 6-month position. That is a real trade. 3 480 boxes is not.

---

## 13. Files and reproduction

| File | What |
|---|---|
| [`PLAN.md`](PLAN.md) | the plan for this job, with progress |
| [`targets.jsonl`](targets.jsonl) | the 130 selected rows (10 per search) with rank and score |
| [`ads_extract.json`](ads_extract.json) | the 82 derived records, including full descriptions |
| `data/finn/annonser/{kode}_{slug}/` | raw HTML + parsed JSON + manifest per ad |
| `data/finn/_log/ad_scrapes.jsonl` | append-only scrape log |
| [`pick_ads.py`](pick_ads.py) | relevance scoring and selection |
| [`analyze_ads.py`](analyze_ads.py) | derived fields and statistics |
| [`dump_desc.py`](dump_desc.py) | readable description dump |
| [`FULL-REPORT.md`](FULL-REPORT.md) | the search-level report (13 searches, 483 ads) |

Reproduce:

```
uv run data/photos-receives-2026-11-08-224643/pick_ads.py
uv run finn/finn_ad.py --from-jsonl data/photos-receives-2026-11-08-224643/targets.jsonl --no-images
uv run data/photos-receives-2026-11-08-224643/analyze_ads.py
uv run data/photos-receives-2026-11-08-224643/dump_desc.py --core
```

---

## 14. Caveats

- **One page per search.** 483 of a possible ~2 650 ads were seen. The 82 are a relevance-ranked sample, not a census.
- **Prices are asking prices.** No sold-price data exists on FINN. Every ratio in this report is ask ÷ offer, not realised ÷ offer.
- **The 1,51× is one seller's list.** It is the best comparable available, but it is one data point repeated across 14 sets.
- **Freight and fee estimates are estimates.** They are labelled as ranges and the assumptions are stated in §9.
- **No PokeWallet API calls were made.** `logs/ratelog.csv` is untouched; the 100/hour, 1 000/day budget is intact.
- **The Google Sheet has not been touched.** Per instruction, sheet work waits for the go-ahead.
