# AGENTS.md

Instructions for any AI agent (Roo, Claude, Codex, ...) working in this repository. Read this before doing anything.

---

## What this repo is

This repo grew out of a Pokémon-card project around FINN.no listings: ad captures, collection exports, scanned-card CSVs, price/droprate research and tracker ideas. As of commit `0ccc05c` it **pivoted** to one clear purpose: turning **finn.no into structured data** — a pipeline that scrapes FINN.no listings, parses them into machine-read fields, and lands them in an append-only archive and a Google Sheet.

The **FINN-kode** (the numeric ad id, e.g. `475878513`) is the primary key for everything: folders, rows, dedupe, image downloads.

The pipeline specification is [`scraper-parser-spec.md`](scraper-parser-spec.md) — read it before doing any pipeline work. **Division of responsibility:** this file says *how to act* in this repo (workspace + tool rules, repo map); the spec says *what we are building and why*. The pipeline philosophy is stated **only** in the spec (§0) — never duplicated here, so the two cannot drift apart.

---

## Workspace principles (non-negotiable — how you behave here, pipeline or not)

1. **We never delete anything. Ever.** Not in git, not on disk. Removing a file from the working tree means moving it to a `.trash/` folder **in the same directory** (e.g. `docs/foo.md` → `docs/.trash/foo.md`). Never dump into one global trash folder.
2. **No silent success.** Never suppress errors. Never print "operation completed successfully" without actually verifying it. All output is shown, everything is visible.

The pipeline philosophy — append-only log, immutable scraped sources, save everything, versioned producers/outputs, two kinds of data — lives **exactly once**, in [`scraper-parser-spec.md` §0](scraper-parser-spec.md).

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

---

## ⚠️ OPEN REVIEW SECTION (for the human — decide, then edit or delete this section)

Things the AI that wrote this file flagged for your review. None of these are decided yet.

### Session rules I made permanent here — confirm or strike:
- [ ] **"Never read `prompts-notes/prompts.md`"** — that was a session instruction, not necessarily repo law. Keeping it means every agent tool refuses that file forever.
- [ ] **"Git is read-only by default"** — came from session feedback; confirm you want it as standing policy for all agents.
- [ ] **"Use long flags"** — same; style rule, your call.
- [ ] **"Never modify the user's rules"** — phrase is ambiguous in a repo file ("whose rules?"). Clearer wording would be "do not edit the rules sections of this file".

### Duplication / drift risk:
- [x] **RESOLVED (restructured):** the philosophy is no longer duplicated. Workspace principles (never delete, no silent success) stay here; the pipeline philosophy (append-only, immutable sources, save everything, versioned producers, two kinds of data) lives only in [spec §0](scraper-parser-spec.md).
- [ ] Sheet ID, `web_to_md.py` path, uv rules also live in the owner's global agent config. Repetition only matters if you use tools that read *only* this file (Codex etc.).

### Overlap with the owner's global rules (what is a pure duplicate?):
Rules here that Roo already enforces globally from `~/.roo/rules/` — duplicated on purpose *if* non-Roo tools (Codex etc.) will use this repo, pure noise if Roo-only:
- [ ] **uv run / `uv add --script` / never hand-edit PEP 723** → duplicates `python-env-rules.md` (verbatim).
- [ ] **"File operations must fail rather than overwrite"** → duplicates universal-rules "Moving/Renaming files".
- [ ] **"Never modify the user's rules"** → duplicates universal-rules "Do not modify the rules".
- [ ] **"Never delete anything / .trash in the same directory"** → duplicates universal-rules "Never delete files".
- [ ] **"No silent success"** → duplicates universal-rules "Never suppress errors" (+ the success-print clause).
Not covered by global rules (repo/session-specific — these are the ones only this file carries):
- Git read-only by default; long flags.
- Never read `prompts-notes/prompts.md`.
- `web_to_md.py --js` scraping rule.
- Append-only pipeline, immutable sources, versioned producers, two-kinds-of-data, sheet/finn-kode specifics (the genuinely repo-own rules).

### Aging hazards:
- [ ] The `0ccc05c` reference will read as stale trivia later; could become "the pivot commit in the git history".

### Possibly missing:
- [ ] A `getcollectr/README.md` recording the original Downloads filenames + the two source URLs (provenance; currently only in chat history).
- [ ] Language preference (respond in English; Norwegian where mirroring FINN content).
- [ ] Windows/cmd environment note (cmd.exe, `findstr` not `grep`, real paths — no symlinks).
- [ ] Warning that `.git` holds ~242 MiB of dead loose objects from the undone commit `250c9ef` (binaries) — so a future agent doesn't "helpfully" run `git gc`; cleanup is the human's call (reflog expire + gc).
