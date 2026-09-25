# AGENTS.md

Instructions for any AI agent (Roo, Claude, Codex, ...) working in this repository. Read this before doing anything.

---

## What this repo is

This repo was originally a FINN.no Pokémon-card arbitrage project. As of commit `0ccc05c` it **pivoted**: it is now about turning **finn.no into structured data** — a pipeline that scrapes FINN.no listings, parses them into machine-read fields, and lands them in an append-only archive and a Google Sheet.

The **FINN-kode** (the numeric ad id, e.g. `475878513`) is the primary key for everything: folders, rows, dedupe, image downloads.

The pipeline specification is [`scraper-parser-spec.md`](scraper-parser-spec.md) — read it first. Its §0 ("Non-negotiable principles") is the constitution for this whole repo, not just the scraper.

---

## The philosophy (non-negotiable, applies to everything)

1. **We never delete anything. Ever.** Not in git, not on disk, not in the pipeline. Removing a file from the working tree means moving it to a `.trash/` folder **in the same directory** (e.g. `docs/foo.md` → `docs/.trash/foo.md`). Never dump into one global trash folder.
2. **Append-only.** The pipeline is effectively an append-only log. History is never mutated; changes are visible as new entries, not silent edits.
3. **Scraped sources are immutable.** Raw captures are archives. Fix a parser bug → re-run the parser on the same raw file. Never edit a capture.
4. **Save everything.** Every part of the pipeline saves its output, always. There is no such thing as a "progress point" to lose: every completed capture is durable the moment it is written.
5. **Version the producer, version the output.** Parsers/tools are versioned and each output row records what produced it. Updating a parser never silently rewrites old values — a human may be referencing the data.
6. **Two kinds of data** (see spec §2.0): machine-read (parser only, append-only) and derived (LLM/human, in their own clearly-labeled columns). **A writer never touches a column owned by another writer.**
7. **No silent success.** Never suppress errors. Never print "operation completed successfully" without actually verifying it. All output is shown, everything is visible.

---

## Hard rules for agents

- **Git is read-only by default.** Never `commit`, `reset`, `push`, `add`, `checkout`, etc. unless the user explicitly asks. Inspecting (`status --porcelain --untracked-files=all`, `log --oneline`, `show`, ...) is fine. Use **long flags** (`git status --branch --short`, not `-sb`).
- **Never read [`prompts-notes/prompts.md`](prompts-notes/prompts.md)** unless the user explicitly asks. Other files in `prompts-notes/` are fine.
- **Python:** always run scripts with `uv run script.py`. Never `python`, `pip install`, `uv pip install`, or `uv run --with`. Third-party dependencies are added with `uv add --script` (never hand-edit the PEP 723 `# /// script` block).
- **Scraping:** use `C:\data\code\93andresen_Scripts\web_to_md.py` via `uv run ... --js` (JS rendering is mandatory — Block B is a strict superset of Block A).
- **File operations must fail rather than overwrite.** Moves/renames/copies must never be able to clobber an existing file, including files you cannot see.
- **Never modify the user's rules.** If a rule seems wrong, explain what a change would look like so the user can apply it themselves.

---

## Repo map

| Path | What it is |
|---|---|
| [`scraper-parser-spec.md`](scraper-parser-spec.md) | The pipeline spec — scraping, parsing, data-ownership rules, spreadsheet ingestion. Read first. |
| [`prompts-notes/`](prompts-notes) | Human-written prompts and notes (incl. the original brief this spec grew out of). `prompts.md` is off-limits. |
| [`docs/`](docs) | Pokewallet API reference docs. |
| [`pokewallet-api-ideas/`](pokewallet-api-ideas) | Pre-pivot ideas (Pokewallet API, tracker plan) — history, superseded by the spec. |
| [`pokewallet-api-ideas-prompts/`](pokewallet-api-ideas-prompts) | Pre-pivot prompts — history. |
| [`getcollectr/`](getcollectr) | Collectr (app.getcollectr.com) collection exports for Marius' cards (HTML, various sort/view combos). |
| [`s21-silver-downloads/`](s21-silver-downloads) | Scanned-card exports (CSV) and research material. Some subfolders are gitignored (see `.gitignore` below the repo-specific marker line). |
| [`llm-history/`](llm-history) | Imported LLM chat logs. |
| [`.trash/`](.trash) | Everything ever removed from the working tree. Never emptied. |
| [`repo_overview.py`](repo_overview.py) | Read-only git overview script (`uv run repo_overview.py`); only runs whitelisted git commands. |
| [`.gitignore`](.gitignore) | Repo-specific ignores go **below** the marker line: `# Repo-Spesific ignores (ALL EDITS TO THIS FILE SHOULD BE BELOW THIS LINE)`. |

---

## When adding files

- Scraped material and exports belong in their topical folders (`finn/annonser/{FINN-kode}_{slug}/` for ads once the pipeline exists; downloads/exports in their named folders).
- New top-level structure decisions should be recorded in the spec or in a commit message explaining the **why** — this repo values documented intent over tribal knowledge.
