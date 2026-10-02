# Naming inventory — `marius … pokemon / kort / cards` strings

Search performed over `c:/data/code/marius-pokemonkort` on **2026-10-02**.

Goal: find every place where a string in the family of
`marius-pokemon-cards`, `marius-pokemonkort`, `marius-pokemon-kort`,
`marius_pokemon_cards`, `marius_pokemonkort` (and casing/separator variants)
appears in **folder names**, **file names** and **file contents**.

## Method / scope

- **Names:** `Get-ChildItem -Recurse -Force` across the whole working tree,
  including `.history/`, `.trash/` and `.git/` internals.
- **Contents:** recursive regex search (case-insensitive) for `marius` and for the
  pokemon/kort/cards variants, run over all text files.
- **Not text-searchable:** `.git` object blobs are compressed/binary — only its
  plain-text internals (`config`, `FETCH_HEAD`, `logs/*`) were readable.
- `.history/` is VS Code *Local History* and is **gitignored** (see [`.gitignore`](.gitignore:2)),
  so it is snapshot noise, not tracked repo content, but it is reported below for completeness.

## Headline numbers

| Measure | Count |
|---|---|
| Files **named** with a `marius…` string | **16** |
| Files whose **content** contains `marius` (excluding `.git`) | **186** |
| … of those, under `.history/` | **173** |
| Distinct separator/casing variants actually present | **5** |
| Requested variants that **do not exist anywhere** | **2** |

---

## 1. The repo itself carries the name

- The workspace/repo folder is literally named `marius-pokemonkort`.
- Git remote ([`.git/config`](.git/config:9), [`.git/FETCH_HEAD`](.git/FETCH_HEAD:1)):
  `https://github.com/93andresen/marius-pokemonkort.git`
- Commit message in the reflog ([`.git/logs/HEAD`](.git/logs/HEAD:15),
  [`.git/logs/refs/heads/main`](.git/logs/refs/heads/main:14)):
  `scraped Marius' current pokemon card portfolio`

---

## 2. Variants — found vs. not found

| Variant | Present? | Where |
|---|---|---|
| `marius-pokemonkort` | ✅ | Repo folder, git remote, hundreds of `C:\data\code\marius-pokemonkort\…` path references |
| `marius_pokemon_cards` | ✅ | [`getcollectr/marius_pokemon_cards_collectr_export_2026-10-02-052742.csv`](getcollectr/marius_pokemon_cards_collectr_export_2026-10-02-052742.csv) + referenced in [`prompts-notes/prompts.md`](prompts-notes/prompts.md:327) |
| `marius-pokemon-cards` | ✅ | Old folder name recorded in the knowledge-base notes ([`.trash/repo-knowledge.md`](.trash/repo-knowledge.md:225)) |
| `marius_pokemon_<timestamp>` | ✅ | 11 scanned-card CSV exports (see §3) |
| `marius2_<timestamp>` | ✅ | 4 scanned-card CSV exports (see §3) |
| `Marius'` / `Marius's` (owner name) | ✅ | [`AGENTS.md`](AGENTS.md:46), [`prompts-notes/prompts.md`](prompts-notes/prompts.md:302), Collectr HTML, reflog |
| `marius-pokemon-kort` | ❌ | **0 matches anywhere** |
| `marius_pokemonkort` | ❌ | **0 matches anywhere** |
| `marius pokemonkort` | ❌ | **0 matches anywhere** |
| `mariuspokemonkort` | ❌ | **0 matches anywhere** |

So although `marius-pokemon-kort` and `marius_pokemonkort` look like natural
variants, they were **never used** in this repo. The two surviving forms are
`marius-pokemonkort` (repo paths) and `marius_pokemon_cards` (export filenames).

---

## 3. Filenames & folder names

### 3a. Names containing `marius` (16 files)

**getcollectr/**
- [`marius_pokemon_cards_collectr_export_2026-10-02-052742.csv`](getcollectr/marius_pokemon_cards_collectr_export_2026-10-02-052742.csv)

**s21-silver-downloads/exports-of-the-cards-scanned-by-richard/**
- [`marius_pokemon_030426_090049.csv`](s21-silver-downloads/exports-of-the-cards-scanned-by-richard/marius_pokemon_030426_090049.csv)
- [`marius_pokemon_030426_100147.csv`](s21-silver-downloads/exports-of-the-cards-scanned-by-richard/marius_pokemon_030426_100147.csv)
- [`marius_pokemon_030426_100208.csv`](s21-silver-downloads/exports-of-the-cards-scanned-by-richard/marius_pokemon_030426_100208.csv)
- [`marius_pokemon_030426_100221.csv`](s21-silver-downloads/exports-of-the-cards-scanned-by-richard/marius_pokemon_030426_100221.csv)
- [`marius_pokemon_030426_100238.csv`](s21-silver-downloads/exports-of-the-cards-scanned-by-richard/marius_pokemon_030426_100238.csv)
- [`marius_pokemon_030426_100245.csv`](s21-silver-downloads/exports-of-the-cards-scanned-by-richard/marius_pokemon_030426_100245.csv)
- [`marius_pokemon_030426_100301.csv`](s21-silver-downloads/exports-of-the-cards-scanned-by-richard/marius_pokemon_030426_100301.csv)
- [`marius_pokemon_030426_100308.csv`](s21-silver-downloads/exports-of-the-cards-scanned-by-richard/marius_pokemon_030426_100308.csv)
- [`marius_pokemon_030426_153000.csv`](s21-silver-downloads/exports-of-the-cards-scanned-by-richard/marius_pokemon_030426_153000.csv)
- [`marius_pokemon_cards_pricecharting_export_scanned_by_richard_collection_20261002.csv`](s21-silver-downloads/exports-of-the-cards-scanned-by-richard/marius_pokemon_cards_pricecharting_export_scanned_by_richard_collection_20261002.csv)
- [`marius_pokemon_copy_030426_160233.csv`](s21-silver-downloads/exports-of-the-cards-scanned-by-richard/marius_pokemon_copy_030426_160233.csv)
- [`marius2_030426_090115.csv`](s21-silver-downloads/exports-of-the-cards-scanned-by-richard/marius2_030426_090115.csv)
- [`marius2_030426_100112.csv`](s21-silver-downloads/exports-of-the-cards-scanned-by-richard/marius2_030426_100112.csv)
- [`marius2_030426_153010.csv`](s21-silver-downloads/exports-of-the-cards-scanned-by-richard/marius2_030426_153010.csv)
- [`marius2_copy_030426_153703.csv`](s21-silver-downloads/exports-of-the-cards-scanned-by-richard/marius2_copy_030426_153703.csv)

> **Note:** the export CSVs themselves do **not** contain the string `marius` inside —
> it appears only in their filenames.

### 3b. Related `pokemon` / `kort` names *without* `marius` (nearest neighbours)

These do not contain `marius`, but they are the same subject matter and are the
other places a rename would touch:

- [`.trash/finn/annonser/Pokemon_kort/`](.trash/finn/annonser/Pokemon_kort)
  (incl. [`Pokemon_kort.md`](.trash/finn/annonser/Pokemon_kort/Pokemon_kort.md:24))
- [`.trash/finn/annonser/Pokemonkort_-_79_stk_reverse_holo/`](.trash/finn/annonser/Pokemonkort_-_79_stk_reverse_holo)
- [`.trash/finn/annonser/High-End_-_Pokemon_kort_pakker_med_vintage_hits_og_ex_kort!_Beste_på_markedet/`](.trash/finn/annonser/High-End_-_Pokemon_kort_pakker_med_vintage_hits_og_ex_kort!_Beste_på_markedet)
- [`pokewallet-api-ideas/pokemon-card-collection-tracker-plan.md`](pokewallet-api-ideas/pokemon-card-collection-tracker-plan.md)
- [`pokewallet-api-ideas-prompts/design-pokemon-card-collection-tracker-spreadsheet.md`](pokewallet-api-ideas-prompts/design-pokemon-card-collection-tracker-spreadsheet.md)
- [`pokewallet-api-ideas-prompts/design-pokemon-card-collection-tracker-spreadsheet-no-tools.md`](pokewallet-api-ideas-prompts/design-pokemon-card-collection-tracker-spreadsheet-no-tools.md)
- [`pokewallet-api-ideas-prompts/design-pokemon-card-collection-tracker-spreadsheet-rewritten-for-browser-llms.md`](pokewallet-api-ideas-prompts/design-pokemon-card-collection-tracker-spreadsheet-rewritten-for-browser-llms.md)
- [`pokewallet-api-ideas-prompts/design-pokemon-card-collection-tracker-spreadsheet-rewritten-for-browser-llms-original.md`](pokewallet-api-ideas-prompts/design-pokemon-card-collection-tracker-spreadsheet-rewritten-for-browser-llms-original.md)
- [`llm-history/openrouter-chat-import-pokemon-1.md`](llm-history/openrouter-chat-import-pokemon-1.md), [`…-1-exported.json`](llm-history/openrouter-chat-import-pokemon-1-exported.json), [`…-2.md`](llm-history/openrouter-chat-import-pokemon-2.md), [`…-2-exported.json`](llm-history/openrouter-chat-import-pokemon-2-exported.json)
- [`prompts-notes/old/research-prompt-pokemon-arbitrage-norway.md`](prompts-notes/old/research-prompt-pokemon-arbitrage-norway.md)
- [`s21-silver-downloads/finding-resources-and-apps-for-scanning-cards-and-fetching-values/Best resource for all pokemon card values-perplexity.md`](s21-silver-downloads/finding-resources-and-apps-for-scanning-cards-and-fetching-values/Best%20resource%20for%20all%20pokemon%20card%20values-perplexity.md)
- `getcollectr/scraped/` → 4 HTML captures (see §4a)

---

## 4. File contents containing `marius…`

### 4a. Active / tracked files (13 files)

**Root**
- [`AGENTS.md`](AGENTS.md:46) — `…for Marius' cards (HTML, various sort/view combos).`

**prompts-notes/** (3 files)
- [`prompts-notes/prompts.md`](prompts-notes/prompts.md:11) — plus repeated `C:\data\code\marius-pokemonkort\…` paths at
  lines [`23`](prompts-notes/prompts.md:23), [`31`](prompts-notes/prompts.md:31), [`32`](prompts-notes/prompts.md:32), [`153`](prompts-notes/prompts.md:153), [`184`](prompts-notes/prompts.md:184), [`187`](prompts-notes/prompts.md:187), [`223`–`247`](prompts-notes/prompts.md:223);
  the old Collectr export filenames `Marius's Pokemon Trading Card Collection - Collectr (…)` at
  [`302`–`308`](prompts-notes/prompts.md:302); and the getcollectr CSV path at [`327`](prompts-notes/prompts.md:327).
- [`prompts-notes/notes.md`](prompts-notes/notes.md:13) — `C:\data\code\marius-pokemonkort\research-prompt-pokemon-arbitrage-norway.md`
- [`prompts-notes/scraper-parser-spec-prompt.md`](prompts-notes/scraper-parser-spec-prompt.md:37) —
  three `…\marius-pokemonkort\finn\annonser\…` command examples (lines [`37`](prompts-notes/scraper-parser-spec-prompt.md:37), [`42`](prompts-notes/scraper-parser-spec-prompt.md:42), [`44`](prompts-notes/scraper-parser-spec-prompt.md:44))

**pokewallet-api-ideas-prompts/** (4 files)
- [`pokewallet-api-ideas-prompt-for-browser-llm.md`](pokewallet-api-ideas-prompts/pokewallet-api-ideas-prompt-for-browser-llm.md:2) — lines [`2`](pokewallet-api-ideas-prompts/pokewallet-api-ideas-prompt-for-browser-llm.md:2), [`6`](pokewallet-api-ideas-prompts/pokewallet-api-ideas-prompt-for-browser-llm.md:6), [`46`](pokewallet-api-ideas-prompts/pokewallet-api-ideas-prompt-for-browser-llm.md:46)
- [`pokewallet-api-ideas-prompt-for-agent.md`](pokewallet-api-ideas-prompts/pokewallet-api-ideas-prompt-for-agent.md:2) — lines [`2`](pokewallet-api-ideas-prompts/pokewallet-api-ideas-prompt-for-agent.md:2), [`5`](pokewallet-api-ideas-prompts/pokewallet-api-ideas-prompt-for-agent.md:5)
- [`design-pokemon-card-collection-tracker-spreadsheet.md`](pokewallet-api-ideas-prompts/design-pokemon-card-collection-tracker-spreadsheet.md:24)
- [`design-pokemon-card-collection-tracker-spreadsheet-no-tools.md`](pokewallet-api-ideas-prompts/design-pokemon-card-collection-tracker-spreadsheet-no-tools.md:26)

**getcollectr/scraped/** (4 files — minified HTML, match sits on the long line 5)
- [`grid_date-added_newest-first.html`](getcollectr/scraped/grid_date-added_newest-first.html:5)
- [`grid_date-added_oldest-first.html`](getcollectr/scraped/grid_date-added_oldest-first.html:5)
- [`list_date-added_newest-first.html`](getcollectr/scraped/list_date-added_newest-first.html:5)
- [`list_date-added_oldest-first.html`](getcollectr/scraped/list_date-added_oldest-first.html:5)

  These embed the export title `Marius's Pokemon Trading Card Collection - Collectr`.

### 4b. `.trash/` (1 file)
- [``.trash/repo-knowledge.md`](.trash/repo-knowledge.md:1) — repo name `marius-pokemonkort` (lines [`1`](.trash/repo-knowledge.md:1), [`86`](.trash/repo-knowledge.md:86)) and the old folder/paths
  `scrapes-s21-silver/s21-silver-downloads/marius-pokemon-cards/…`,
  `marius*_030426_*.csv` (lines [`225`](.trash/repo-knowledge.md:225), [`226`](.trash/repo-knowledge.md:226), [`228`](.trash/repo-knowledge.md:228)).

### 4c. `.history/` (173 files, gitignored VS Code Local History)
Every snapshot of the files above shows up here. Distinct string patterns found:
- `C:\data\code\marius-pokemonkort\…` — dozens of `notes_*`, `prompts_*`, `task_*`,
  `prompts-notes/*`, `prompts-and-notes/*`, `scraper-parser-spec-prompt_*` snapshots.
- `Marius's Pokemon Trading Card Collection - Collectr (…)` — many `task_*` / `prompts_*` snapshots.
- `marius-pokemonkort` + `marius-pokemon-cards` — [`repo-knowledge_*.md`](.history/repo-knowledge_20260925195004.md:1) snapshots.
- `Marius' cards` — [`AGENTS_*.md`](.history/AGENTS_20260925203309.md:49) snapshots.
- `de2124639… commit: scraped Marius' current pokemon card portfolio` — in
  [`.history/.git/COMMIT_MSG_*.txt`](.history/.git/COMMIT_MSG_20260925200253.txt:32).

### 4d. `.git/` internals (plain-text files)
- [`.git/config`](.git/config:9), [`.git/FETCH_HEAD`](.git/FETCH_HEAD:1) — remote URL `…/marius-pokemonkort`
- [`.git/logs/HEAD`](.git/logs/HEAD:15), [`.git/logs/refs/heads/main`](.git/logs/refs/heads/main:14) — commit message with `Marius'`

---

## 5. The five distinct exact strings actually in use

| # | Exact string | Kind | Representative location |
|---|---|---|---|
| 1 | `marius-pokemonkort` | repo path / remote | `.git/config`, all `prompts-notes` / `pokewallet-api-ideas-prompts` path refs |
| 2 | `marius_pokemon_cards` | export filename | `getcollectr/marius_pokemon_cards_collectr_export_2026-10-02-052742.csv` |
| 3 | `marius-pokemon-cards` | old folder name | `.trash/repo-knowledge.md:225` |
| 4 | `marius_pokemon_<timestamp>` / `marius_pokemon_copy_…` | export filenames | `s21-silver-downloads/exports-of-the-cards-scanned-by-richard/` |
| 5 | `marius2_<timestamp>` / `marius2_copy_…` | export filenames | same folder |

Plus the human-readable title/owner forms:
`Marius's Pokemon Trading Card Collection - Collectr` and `Marius' cards`.

---

## 6. Where the requested variants are **absent**

A dedicated search for these returned **zero** results across the entire repo
(names and contents, including `.history` and `.git` text files):

- `marius-pokemon-kort`
- `marius_pokemonkort`
- `marius pokemonkort`
- `mariuspokemonkort`

---

## 7. Practical note for a rename

If the intent is to rename the repo/card-export naming, the **live** (non-`gitignored`)
touch-points are:

1. Folder name `marius-pokemonkort` (the repo root itself).
2. Git remote URL in [`.git/config`](.git/config:9).
3. 16 file names (§3a) — 1 in `getcollectr/`, 15 in
   `s21-silver-downloads/exports-of-the-cards-scanned-by-richard/`.
4. Hard-coded absolute paths `C:\data\code\marius-pokemonkort\…` inside
   [`prompts-notes/prompts.md`](prompts-notes/prompts.md:11),
   [`prompts-notes/notes.md`](prompts-notes/notes.md:13),
   [`prompts-notes/scraper-parser-spec-prompt.md`](prompts-notes/scraper-parser-spec-prompt.md:37) and the four
   [`pokewallet-api-ideas-prompts/`](pokewallet-api-ideas-prompts) files.
5. Prose `Marius' cards` in [`AGENTS.md`](AGENTS.md:46).

`.history/`, `.trash/` and `.git` blobs are archival/history and would not normally
be rewritten (and `.history/` is gitignored anyway).
