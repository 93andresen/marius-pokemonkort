# AGENTS.md — the always-on bootstrap

> **This file is auto-loaded into every agent's context.** Keep it short and high-signal; it is the
> one file you are guaranteed to have. Everything deeper is read *on demand* (see §1).
> If your context was summarized / compacted mid-task: **re-read your `work/<id>/TASK.md`**, then
> continue from `RESULT.md`/your notes. Do **not** re-explore the repo to "catch up" (§1).

---

## 0. What this repo is (20 seconds)

One repo, two intertwined products:

- **A — Portfolio pricing.** Price Marius' Collectr card export against the **PokeWallet API**
  (free budget: **100 req/hour, 1000/day**), snapshot prices over time, publish to a Google Sheet.
- **B — FINN.no toolkit** *(the real prize)*. Scrape [finn.no](https://www.finn.no) Pokémon listings into
  **structured JSON** (never Markdown — retired 2026-10-02), match them to PokeWallet cards, and overlay
  market prices while browsing.

The **FINN-kode** (numeric ad id, e.g. `475878513`) is the primary key everywhere: folders, rows, dedupe,
images.

## 1. Context protocol — the #1 rule

Context budget is the scarcest resource; a task must start lean. Reading the whole repo to "catch up" is
the failure this file exists to prevent.

1. **Default reading set = this file + your task brief (`work/<id>/TASK.md`). Nothing else.**
2. Open any *other* file **only when the brief names it**, and read the smallest slice that answers the
   question (`offset`/`limit`, not whole files).
3. **Do not read `PROJECT-PLAN.md` or `scraper-parser-spec.md` end-to-end.** They are the archival record
   of the whole project, not task inputs. Use the compact map in §3 or `search_files` (grep) to find the
   one section you need.
4. **Do not re-read a file you already read this task.**
5. Target: be ready to *work* well under **40k tokens** of context. If catching up costs more than the
   task itself, stop and report that the brief is under-specified — don't keep reading.
6. **After compaction/summarization:** `work/<id>/TASK.md` (goal + success criteria + test plan) and
   `RESULT.md` (evidence + status) are the source of truth. Re-read them, then continue. Never restart
   from scratch.

## 2. Never read / never touch

- `prompts-notes/` is readable — `prompts.md` is the human source of the FINN search catalog
  (`finn/finn_searches.py`); `notes.md` is user-owned (read it, never write to it).
- Bulk/raw data is **not context**: `data/**`, `llm-history/**`, `.history/**`, `getcollectr/scraped/**`,
   `s21-silver-downloads/**`. Read a *sample* only if the task requires it.
- `.trash/**` — archive of removed files; ignore unless hunting history on purpose.
- Do not edit `AGENTS-suggestions.md` (advisory, possibly wrong) or `prompts-notes/notes.md` (user-owned).

## 3. Repo map (compact)

| Path | What |
|---|---|
| `AGENTS.md` | this bootstrap (always loaded) |
| `WORKFLOW.md` | how work is done here — **read once per task** |
| `work/` | one folder per work item (`TASK.md` + `RESULT.md`); `work/README.md`, `work/TEMPLATE.md` |
| `tests/` | tests; see `tests/README.md` for conventions |
| `finn/` | FINN scrapers + matcher: `finn_search.py`, `finn_ad.py`, `finn_matcher.py`, `finnlib.py`, `finn_searches.py` |
| `pokewallet/` | PokeWallet API client + portfolio tools; shared code in `pokewallet/pwlib/` |
| `sheet/` | `build_sheet.py` (Sheet payloads) + `AppScript.gs` (formatting) |
| `tools/` | browser overlay: `finn-enhance.user.js`, `local_agent.py`, `history_logger.py` (+ `tools/README.md`) |
| `data/` | append-only local data: raw API responses, raw scrapes, snapshots — never delete |
| `docs/` | PokeWallet API docs; `*-VERIFIED-NOTES.md` = live-verified facts (trust over the API docs) |
| `logs/` | append-only run logs (`ratelog.csv`) |
| `PROJECT-PLAN.md`, `scraper-parser-spec.md` | deep archival docs — on demand only (see §1, rule 3) |

## 4. Hard rules (condensed — these override convenience)

- **Run Python with `uv run <script>.py`.** Never `python`, `pip install`, `uv pip install`,
  `uv run --with`, or `uv run python`.
- **Add dependencies via the `uv-dependency-injector` skill** (`uv add --script`). Never hand-edit a
  PEP 723 `# /// script` block.
- **Never delete a file.** Move it to a `.trash/` folder **in the same directory**.
- **Never suppress errors.** No "completed successfully" unless you actually verified it. Print counts and
  compare to expectations; surface mismatches loudly.
- **Writes must fail rather than overwrite** an existing file (especially moves/renames).
- **Idempotent & resumable by default** — check before doing; re-runs must be safe.
- **Timestamps:** `%Y-%m-%d-%H%M%S` (24h, leading zeros, filename-safe, lexically sortable).
- **Git is read-only unless the user asks.** Inspect freely; never commit/reset/checkout on your own.
- **Never edit a test to make it pass.** A red test is a finding — see `WORKFLOW.md` §4.
- **Never modify the user's rules** (`~/.roo/rules/**`) or this file's rule sections; propose changes.

## 5. How work gets done here

**One small, self-contained unit at a time.** Before coding, an agent writes its own task brief with the
**success criteria and the tests it will write first** — nobody pre-decides the output for you. Then:
implement end-to-end, run the tests, capture real evidence, record it in `RESULT.md`.
Method: [`WORKFLOW.md`](WORKFLOW.md). Work-item scaffold: [`work/README.md`](work/README.md).

## 6. Canonical IDs & endpoints (do not lose)

```
Google Sheet ID       : 13TfMos8hP4zT3-Tf92F7ZE0hJ2r7cKJdEqvdj0gvtpM
  link                : https://docs.google.com/spreadsheets/d/13TfMos8hP4zT3-Tf92F7ZE0hJ2r7cKJdEqvdj0gvtpM/edit
Google Apps Script ID : 1zuV63oR_FZN1NRxlpgsrx5cFUuPc3p4ZgR2_pEZ8GZvJwvZEj6y2yUtr
  link                : https://script.google.com/u/0/home/projects/1zuV63oR_FZN1NRxlpgsrx5cFUuPc3p4ZgR2_pEZ8GZvJwvZEj6y2yUtr/edit
PokeWallet base URL   : https://api.pokewallet.io
PokeWallet auth       : header  X-API-Key: <key>   (env var API_KEY_POKEWALLET)
Rate limits           : 100/hour, 1000/day  (cached responses still count)
```

**Never commit the API key.** Scripts must read it from the `API_KEY_POKEWALLET` env var.
Do not hard-code the Sheet/Apps Script IDs either — read them from config/env with these as defaults.

