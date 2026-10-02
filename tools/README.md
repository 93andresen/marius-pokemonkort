# `tools/` — browser augmentation for finn.no

This folder turns finn.no into a Pokémon price-shopping tool. While you browse
finn.no normally, every Pokémon listing gets an **instant market-price overlay**
(matched against PokeWallet) and every ad you look at is **logged** so you can ask
things like *"find all the Pichu's I have looked at in the last 4 weeks."*

Three pieces, each with one job:

| File | Role | Talks to |
|---|---|---|
| `finn-enhance.user.js` | Tampermonkey/Violentmonkey userscript running in your browser. Renders overlays, hotkeys, follows SPA navigation. | `local_agent.py` over `http://127.0.0.1:8765` |
| `local_agent.py` | Tiny loopback HTTP server. Matches a FINN heading to PokeWallet candidates/prices; guards the API budget; writes the history log. | PokeWallet API (`api.pokewallet.io`) |
| `history_logger.py` | Append-only JSONL store of every viewed ad + a query CLI. | disk only |

The userscript is a **thin client**. All heavy lifting (set index, API calls,
cache, budget, history) lives in the Python side, so nothing is duplicated.

---

## Quick start

1. **Start the local agent** (keep it running in a terminal):

   ```bash
   # live: cache-first, budget-aware, shares the free 100/hr pool with fetch_loop.py
   uv run tools/local_agent.py

   # or cache-only (never spends an API call):
   uv run tools/local_agent.py --offline
   ```

   It prints the endpoints and the current budget on startup.

2. **Install the userscript** in Tampermonkey / Violentmonkey:
   open the extension → *Create a new script* → paste `tools/finn-enhance.user.js`
   → save. Then browse [finn.no](https://www.finn.no) (Pokémon category).

3. A toast confirms the agent was found. If the agent is not running you get a
   reminder with the exact command to start it.

---

## What it does on finn.no

- **Search pages** — hover any result card → a badge appears with the estimated
  market value (`~NNN kr`). Green = cheaper than the market estimate, amber =
  priced over it. Click the badge to open the full breakdown panel.
  - `Alt+A` enriches **all visible cards** at once (queued + throttled).
- **Ad pages** — auto-enriches when an ad opens (can be toggled off). The panel
  shows the parsed card, FINN price, estimated market value, the price delta,
  ranked candidates and a PriceCharting search link (marked *unconfirmed*).
- **SPA navigation** — a URL-change observer (`pushState`/`replaceState`/
  `popstate` + a safety poll) re-triggers enrichment without a reload, because
  finn.no is a React app whose URL changes without a page load.
- **History** — every ad you view is appended to
  `data/finn/history/viewed.jsonl` (never rewritten).

### Hotkeys (all `Alt+…`)

| Keys | Action |
|---|---|
| `Alt+E` | Enrich the current ad, or a finn.no link on the clipboard |
| `Alt+Shift+E` | Enrich from the clipboard link explicitly |
| `Alt+A` | Enrich all visible listing cards |
| `Alt+H` | Show viewed-ad history (last 4 weeks) in the panel |
| `Alt+O` | Toggle hover overlays on/off |

The same actions are also in the Tampermonkey menu (right-click the extension
icon), alongside toggles for ad auto-enrich, hover overlays and viewed-ad logging.

---

## Agent HTTP API (all JSON, loopback only)

| Method & path | Purpose |
|---|---|
| `GET /health` | `{ok, version, offline, budget}` — used for the status dot |
| `GET /match` | `?heading=` (required) `&price=&kode=&url=&status=&location=` → matcher overlay payload |
| `POST /log` | body = viewed-ad JSON → appended to the history log |
| `GET /history` | `?since_days=`/`?since_hours=` `&match=&kode=&limit=` → previously viewed ads |

The `/match` payload is exactly what `finn/finn_matcher.py build_overlay()`
returns: `parsed`, `queries`, `candidates[]`, `best`, `value` (with `est_nok`
and `delta_nok`), `pricecharting_url`, `pricecharting_confirmed: false`.

**Budget:** `/match` is cache-first. If the free hourly floor is hit,
`MatcherService` transparently retries cache-only and adds a `budget_note`, so a
hover never errors — it just shows what's already cached.

---

## Querying your browsing history

```bash
# every Pichu ad you looked at in the last 4 weeks
uv run tools/history_logger.py --since-days 28 --match pichu

# one ad by FINN-kode, newest first
uv run tools/history_logger.py --kode 475878513

# machine-readable
uv run tools/history_logger.py --since-days 7 --json
```

---

## Config

Userscript settings live in Tampermonkey storage (menu toggles set them):
`agentUrl` (default `http://127.0.0.1:8765`), `autoEnrichAd`, `autoLog`,
`hoverOverlay`, `throttleMs`.

Agent flags: `--host` (keep on `127.0.0.1`), `--port`, `--offline`,
`--cache-hours`, `--max-candidates`, `--fx-usd`, `--fx-eur`.

---

## Verified

`data/finn/_probe/test_agent.py` boots the real handler on an ephemeral port and
exercises every route. Last run: **13/13 checks passed** (`/health`, `/`,
`/match` offline → 0 calls spent, `POST /log`, `/history` round-trip, 404).
