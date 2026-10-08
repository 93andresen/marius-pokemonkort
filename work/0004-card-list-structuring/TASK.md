# TASK 0004 — Structure enumerated card lists from `description_raw`

- **Status:** done
- **Owner:** Zoo (code mode)
- **Output artifact(s):** `finn/finn_cards.py`, `tests/test_finn_cards.py`
- **Depends on:** 0001 (fixture)

## Goal (one sentence)

Where an ad's description enumerates cards (a `Liste over kort:` block or a bulleted/numbered list),
extract **per-card records with provenance**, and **loudly flag** count mismatches instead of silently
picking one number.

## Why / context

`SCRAPING_PROMPT.md` §5 stage 4: turn enumerated card lists into structured per-card rows with provenance,
and reconcile title-vs-description counts. §11 requires mismatches to be *flagged, never silently resolved*
(a real listing titled "79 stk" whose description says "99 stk" is the motivating example). §9:
`card_list_present = false` unless the text truly enumerates cards.

Real input: `tests/fixtures/finn_ad_475878513.html` — its description contains a `Liste over kort:` block
listing ~57 card names (Venusaur, Mew, MewTwo, Gengar, Jolteon, …).

## In scope

- `find_card_list_block()` — locate the list (explicit marker, else a long bulleted/numbered run).
- `parse_card_line()` — name + optional per-line count (`4x Pikachu`, `Pikachu x3`) + variants
  (`reverse holo`, `holo`, `1st edition`, `shadowless`, `rh`, `psa`), with a global line index.
- `parse_card_list()` — `{card_list_present, marker, cards[], card_line_count, card_count}`.
- `extract_counts()` — stated counts from title/description (`79 stk`, `260+`, `534 kort`).
- `structure(record)` — the per-ad result incl. `flags[]` for every disagreement.
- CLI: `--json FILE`, `--title T --file DESC`, `--from-jsonl FILE [--out]`.

## Out of scope (do NOT touch)

- Matching cards to PokeWallet / pricing (item 0005).
- LLM-based free-text extraction; this is deterministic parsing only.
- The catalog and identify module.

## Success criteria (DEFINE THESE YOURSELF, before coding)

- [ ] Real capture: `card_list_present == true`, marker is `Liste over kort:`, key names present.
- [ ] Each card row carries `name`, `count`, `variants`, `raw` and a **`line_index`** into the description.
- [ ] Per-line counts parsed (`4x Pikachu`→4, `Pikachu x3`→3); default 1.
- [ ] Variants detected and removed from the name.
- [ ] No enumeration ⇒ `card_list_present == false`, `cards == []`.
- [ ] `extract_counts` finds `stk`/`kort`/`+` counts and ignores bare numbers without a unit.
- [ ] `structure` flags title-vs-description disagreement AND stated-vs-parsed disagreement.
- [ ] Boilerplate lines (Frakt/Sendes) after a list do not become cards.

## Test plan (write these tests FIRST — under `tests/`)

| Test | Input | Expected |
|---|---|---|
| `test_real_capture_block` | fixture description | present; marker "Liste over kort:"; ⊇{Venusaur,Mew,Mewtwo,Gengar,Jolteon}; ≥40 rows |
| `test_line_index_is_global` | fixture | row line_index points at the real line in description |
| `test_counts_per_line` | "4x Pikachu\nPikachu x3\nCharizard" | counts 4,3,1 |
| `test_variants` | "Charizard reverse holo\nMew holo\nBlastoise 1st edition" | names stripped; variants recorded |
| `test_no_list` | "Bare a normal ad with no card list." | present False, cards [] |
| `test_bulleted_list` | "- Pikachu\n- Gengar\n… (≥8)" | detected without a marker |
| `test_extract_counts` | "79 stk Pokemon kort", "260+ kort", "pris 100 kr" | [79], [260], [] |
| `test_flags_title_vs_description` | title "79 stk", desc "Liste over kort:\n… \n99 stk" | a flag mentions 79 and 99 |
| `test_stop_boilerplate` | list then "Sendes i toploader" | "Sendes…" not a card |

## Evidence to capture

- `uv run tests/test_finn_cards.py` output (count + OK).
- `uv run finn/finn_cards.py --json data/finn/annonser/475878513_.../475878513.json` real structured rows.
- `uv run finn/finn_cards.py --from-jsonl <run>/all_ads.jsonl --out ...` real counts.

## Open questions / assumptions

- Card names are extracted **verbatim** (not corrected/normalised) — cleaning/canonicalisation is item 0005.
- Variant detection is token-based on explicit words only; a bare `(R)` is *not* guessed at (avoids wrong claims).
- `structure` never resolves a mismatch: it records all stated counts and the parsed count in `flags`.
