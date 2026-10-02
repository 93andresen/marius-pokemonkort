# DEMO — Pokémon card portfolio + live finn.no price overlay

A 5-minute runbook to show off the whole thing. Three moving parts:

1. **Portfolio tracker** — turns the Collectr CSV into priced card data, snapshots it every hour, and populates a Google Sheet with dashboards you can sort any way.
2. **FINN scrapers** — pull finn.no search results and ad pages (title, price, status, images) as structured JSON, no lossy markdown.
3. **Live overlay** (the goldmine) — while you browse finn.no, every listing gets an instant market-price overlay, and every ad you open is logged so you can ask *"show me all the Pichu's I looked at in the last 4 weeks."*

Repo: `c:/data/code/marius-pokemonkort` · Sheet: <https://docs.google.com/spreadsheets/d/13TfMos8hP4zT3-Tf92F7ZE0hJ2r7cKJdEqvdj0gvtpM/edit>

All Python runs through `uv run` (never bare `python`). Free API budget: **100 calls/hour · 1000/day**, shared by every tool — the loop and the overlay both respect it.

---

## 1. The spreadsheet (the visible "win")

The Google Sheet is populated with the collection, current API prices, CSV values, and derived
overview tabs. Open it:

> <https://docs.google.com/spreadsheets/d/13TfMos8hP4zT3-Tf92F7ZE0hJ2r7cKJdEqvdj0gvtpM/edit>

Tabs: `Collection`, `PriceSnapshots` (append-only history), `Sets`, `CardCatalog`, `Movers`
(gainers/losers), `Coverage`, `Dashboard`, `Config`, `RateLog`, `FINN`.

To (re)build the tab payloads from the latest data:

```bash
uv run sheet/build_sheet.py            # emits JSONL arrays to paste into the Sheet
```

## 2. Portfolio price fetching (runs in the background)

```bash
# one pass over the portfolio (resumable; skips fresh cards)
uv run pokewallet/fetch_prices.py

# keep snapping hourly for up to 8 hours (this is the process to leave running)
uv run pokewallet/fetch_loop.py --max-hours 8 --sleep 900
```

Freshness/merge logic means re-runs cost almost no calls. Every raw API response is saved under
`data/pokewallet/raw/<endpoint>/` (never overwritten, never deleted).

## 3. FINN scrapers (structured, not markdown)

```bash
# search results -> structured JSONL (all 50 pages, filters, sorts)
uv run finn/finn_search.py --query "pokemon" --pages 5

# archive one ad: folder-per-ad with metadata + max-size images + manifest
uv run finn/finn_ad.py --kode 475878513
```

`finn_ad.py` downloads the true max image (`original`, with fallbacks) and writes an append-only
`manifest.json` per ad folder.

## 4. The FINN price overlay (the goldmine)

**Start the local agent** (keep it running):

```bash
uv run tools/local_agent.py            # live: cache-first, budget-aware
# or: uv run tools/local_agent.py --offline   # cache-only, never spends a call
```

**Install the userscript** — Tampermonkey/Violentmonkey → *Create new script* → paste
`tools/finn-enhance.user.js` → save. Then browse finn.no (Pokémon).

What you'll see:
- **Hover any search result** → a badge with the estimated market value (green = listed under the
  estimate, amber = over). `Alt+A` enriches **all** visible cards.
- **Open any ad** → a panel with the parsed card, FINN price, estimated market value, the price
  delta, ranked candidates, and a PriceCharting link (stored, marked *unconfirmed*).
- **Hotkeys:** `Alt+E` (enrich ad / clipboard link), `Alt+Shift+E` (clipboard), `Alt+H` (history),
  `Alt+O` (toggle hover), `Alt+A` (all cards).
- Every ad you view is appended to `data/finn/history/viewed.jsonl`.

Ask the "last 4 weeks" question directly:

```bash
uv run tools/history_logger.py --since-days 28 --match pichu
```

The overlay is driven by `finn/finn_matcher.py` (heading → ranked PokeWallet candidates → NOK
estimate). Drive it from the CLI too:

```bash
uv run finn/finn_matcher.py --heading "Psychic Energy #101 Base Set (1999)" --offline
```

---

## The 60-second script for the friend

1. Open the **Google Sheet** → point at the `Dashboard` / `Movers` tabs. *"This is your whole
   collection, priced from the API, with history filling in every hour."*
2. Show a **finn.no Pokémon search** with the overlay riding along — hover a card, `Alt+A`.
3. Open one **ad** → panel pops with the market value and delta.
4. Run `uv run tools/history_logger.py --since-days 28 --match pichu` → *"and it remembers
   everything you've looked at."*

---

## Where everything lives

| Path | What |
|---|---|
| `pokewallet/pwlib/` | API client, price extraction, set index, config, utils |
| `pokewallet/pokewallet_client.py` | generic CLI for any API endpoint (raw-saving, rate-aware) |
| `pokewallet/sync_sets.py`, `resolve_portfolio.py` | set sync + CSV portfolio resolution (178/191 cards) |
| `pokewallet/fetch_prices.py`, `fetch_loop.py` | resumable price snapshots + hourly orchestrator |
| `sheet/build_sheet.py` | Google Sheet tab payload builder |
| `finn/finn_search.py`, `finn_ad.py` | finn.no search + ad scrapers (structured JSON) |
| `finn/finn_matcher.py` | FINN heading → PokeWallet candidates → prices (overlay payload) |
| `tools/local_agent.py` | loopback HTTP server the userscript calls |
| `tools/finn-enhance.user.js` | the browser overlay |
| `tools/history_logger.py` | append-only viewed-ad history + query CLI |
| `tools/README.md` | full operator guide for the overlay |
| `PROJECT-PLAN.md` | the master plan / resume instructions |
| `docs/pokewallet_io_api-VERIFIED-NOTES.md` | verified API facts + strategies |

Budget tip: if calls run low, run the agent with `--offline` — the overlay still works from cache
and just can't fetch brand-new matches.
