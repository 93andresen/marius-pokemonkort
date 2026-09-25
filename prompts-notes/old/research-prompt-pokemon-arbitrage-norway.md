# Research Prompt: End-to-End Pokemon Card Arbitrage into Norway

## Role
Act as a market research analyst specializing in cross-border e-commerce arbitrage and Norwegian import/trading-card markets. Your job is to find exactly **where the largest arbitrage between the world's cheapest Pokemon card sources and Norwegian resale prices exists — and explain why it exists.**

## Objective
Map the full pipeline end to end:

**Cheapest legal source anywhere → shipping to Norway → all Norwegian import costs → Norwegian market resale price → net profit.**

Every step must be quantified with real, current numbers. The deliverable is a ranked list of arbitrage opportunities, with the single largest one identified and its root cause explained.

## Hard requirements
- **Empirical data only.** All numbers must come from live internet research (current prices, current rates). No assumptions, no guesses, no remembered figures.
- **Verify every number.** Footnote each figure with its source URL and the date it was retrieved.
- If a number cannot be verified, label it `UNVERIFIED` and show the closest verifiable proxy and how far off it might be.
- Show currency conversions explicitly, with the FX rate and date used.

---

## Part 1 — Norwegian import rules and costs (the cost floor)
Research and quantify, with sources:

1. **Customs classification and duty rate** for trading cards / Pokemon sealed product imported into Norway (correct HS/CN code, actual duty % — cards are often duty-free, but verify).
2. **Import VAT (merverdiavgift, 25%)**: when it applies, how it is collected, the VOEC scheme and the 3,000 NOK low-value threshold, and what happens above it.
3. **Fortolling / customs handling fees** per carrier into Norway (Posten/Bring, DHL, UPS, FedEx, DPD) — exact current fee schedules.
4. **The company route (the legal version of "no VAT"):** importing and reselling as a registered Norwegian business (ENK or AS) with VAT registration. Walk through the actual cash-flow math: input VAT on import is deductible, output VAT is charged on sale — show precisely what the effective VAT cost per 100,000 NOK of goods is in this route vs. a private import, and what registration/administrative costs are involved.
5. **Private import thresholds**: at which order values (1,000 / 5,000 / 10,000 / 50,000 / 100,000 NOK) full declaration + VAT + fees apply, and the exact total add-on cost at each level.
6. **Compliance risk (factual, for risk assessment only):** documented penalty scales for underdeclaring or undervaluing commercial goods into Norway across value levels from 1,000 to 1,000,000 NOK. State this as risk information that justifies doing imports fully legally — not as a how-to.

## Part 2 — Source markets: where is it cheapest?
For each candidate source market, per product class, find **actual current prices and availability**:

- **Markets to compare:** Japan, USA, Germany, Poland, Netherlands, UK, Hong Kong/Singapore.
- **Product classes:** current Japanese booster boxes, current English booster boxes, ETBs/collection boxes, hot vintage sealed product, graded singles, raw singles.
- For each: current retail/typical street price, typical discount sites, stock availability.
- **Critical filter:** does the seller actually ship to Norway? Many don't. Record shipping-to-Norway cost per option (tracked/insured), and note alternatives like forwarders where legitimate.

## Part 3 — Norwegian resale market: what can you actually sell at?
- Where Norwegians actually buy Pokemon cards: finn.no, Outland, local card stores, Facebook trading groups, card shows, Cardmarket/TCGPlayer shipping into Norway.
- **Current realized asking prices** (not MSRP, not US prices) per product class in NOK.
- Selling costs: marketplace/payment fees, domestic shipping, and **time-to-sell (velocity)** per product class — a 10% margin that takes 6 months is worse than a 5% margin that takes a week.
- Price trend direction for each product class (rising/falling/flat) based on recent data.

## Part 4 — Arbitrage computation (the core deliverable)
Build a landed-cost → net-profit model for every (source, product) pair:

```
landed cost = product price + shipping + insurance + FX spread
            + customs duty + import VAT (or the company/VAT-deduction route)
            + fortolling fee

net margin  = Norwegian realized sale price
            − marketplace/payment fees − domestic shipping
            − landed cost
```

Rank all pairs by:
1. Net margin %, 2. NOK profit per unit, 3. NOK profit per 10,000 NOK of capital deployed.

**Output a ranked table.** Then answer explicitly:
- Which single (source, product, sales channel) combination has the **largest arbitrage**?
- **Why** does it exist? (e.g., regional MSRP differences, Japanese domestic pricing, FX movements, demand asymmetry between Japan/US and Norway, distribution gaps.) Explain the root cause, and whether it is structural and likely to persist or a temporary dislocation.

Include a **sensitivity scenario**: margins with full private-import VAT paid vs. the VAT-registered business route — showing how much of the spread the VAT layer consumes in each case.

## Part 5 — Scale scenarios
For total order values of **5,000 / 10,000 / 50,000 / 100,000 NOK**, for the top-ranked opportunity:
- Units acquired, total landed cost, expected revenue, net profit.
- Capital velocity (how many turns per month the inventory allows).
- What breaks or gets riskier at each scale (stock depth, sell-through, cash lockup).

## Part 6 — Verdict
- The single best end-to-end play with exact numbers from source to sale.
- Top 3 reasons the arbitrage exists and how durable each is.
- Top 5 risks that would destroy the margin (price crash, FX, shipping loss, demand shift, rule changes).
- A final **"verified vs. unverified"** summary listing every figure's confidence level.

## Output format
Markdown, tables for all comparisons, every figure footnoted with source and retrieval date. If any part cannot be answered with verified current data, say so explicitly rather than estimating silently.
