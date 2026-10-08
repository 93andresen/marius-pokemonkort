# RESULT 0004 — Structure enumerated card lists from `description_raw`

- **Status:** done
- **Owner:** Zoo (code mode)
- **Artifacts:** `finn/finn_cards.py` (new), `tests/test_finn_cards.py` (new),
  `work/0004-card-list-structuring/check_provenance.py` (diagnostic)
- **Depends on:** 0001 (fixture) — satisfied.

## Deliverable

`finn/finn_cards.py` turns an enumerated card list in an ad description into per-card records
**with provenance** and reconciles stated-vs-enumerated counts **loudly**.

Public surface:

- [`logical_lines()`](../finn/finn_cards.py:72) — canonical line split; normalizes every Unicode line
  boundary (LS/PS/CR/VT/FF/NEL) to `"\n"`.
- [`parse_card_line()`](../finn/finn_cards.py:107) — name + per-line count (`4x Pikachu`, `Pikachu x3`)
  + variants (`reverse holo`/`holo`/`1st edition`/`shadowless`/`rh`/`psa`), with a global `line_index`.
- [`find_card_list_block()`](../finn/finn_cards.py:151) — explicit marker (`Liste over kort:`, …) else a
  ≥8-item bullet/numbered run.
- [`parse_card_list()`](../finn/finn_cards.py:193) — `{card_list_present, marker, cards[], card_line_count, card_count}`.
- [`extract_counts()`](../finn/finn_cards.py:213) — stated totals (`79 stk`, `260+`, `534 kort`, `80x kort`).
- [`structure()`](../finn/finn_cards.py:224) — per-ad result + `flags[]` for every disagreement.
- CLI: `--json FILE`, `--title T --file DESC`, `--from-jsonl FILE [--out]`.

## Success criteria — met

- [x] Real capture: `card_list_present == true`, marker `Liste over kort`, key names present.
- [x] Each row carries `name`, `count`, `variants`, `raw`, and a `line_index` into the description.
- [x] Per-line counts parsed; default 1.
- [x] Variants detected and stripped from the name.
- [x] No enumeration ⇒ `card_list_present == false`, `cards == []`.
- [x] `extract_counts` finds `stk`/`kort`/`+` counts, ignores bare numbers with no unit.
- [x] `structure` flags title-vs-description AND stated-vs-parsed disagreement.
- [x] Boilerplate (Frakt/Sendes/…) after a list does not become cards.

## Finding (real bug, found by the provenance test)

The real capture contains a **`U+2028` LINE SEPARATOR (LS)** at offset 508 of `description_raw`
(`"S - Shaddowless Base set\u2028R - Reverse holo"`). `str.splitlines()` splits on it, but the
`line_index` was computed with `str.count("\n")`, which does **not** — so every card after offset 508 was
shifted by one (Venusaur reported at 40, actually at 41).

- `count('\n') = 152`, `len(splitlines) = 154`, `len(split("\n")) = 153`.
- Pre-fix: **57 / 57** card line-indices were wrong. Post-fix: **0 / 57**.

**Fix:** a single canonical split, [`logical_lines()`](../finn/finn_cards.py:72), normalizes LS/PS/CR/VT/FF/NEL
to `"\n"`; both block detection and row iteration use it. The test now asserts provenance in the same
canonical space. The module is self-consistent regardless of which exotic boundary char a real ad carries.

## Evidence

`uv run tests/test_finn_cards.py` → **12 tests, OK** (adds `LogicalLines.test_normalizes_unicode_boundaries`
and a range check in `test_line_index_is_global`).

`uv run work/0004-card-list-structuring/check_provenance.py`:

```
desc length                    = 1287
count('\n')                    = 152
len(logical_lines)  [canonical]= 154
len(splitlines)                = 154
len(split('\n'))     [naive]   = 153
card_line_count                = 57
marker                         = 'Liste over kort'
extra line-boundary chars      = 1
    offset 508: LS

mismatches vs canonical (logical_lines) = 0 / 57   <-- MUST be 0
mismatches vs splitlines                = 0 / 57
mismatches vs naive split('\n')         = 57 / 57   <-- illustrates the pre-fix drift
```

`uv run finn/finn_cards.py --json data/finn/annonser/475878513_.../475878513.json` → 57 card rows,
`line_index` 41,43,…,153 (Venusaur … Magnemite), `card_count=57`, `flags=[]`.

Full suite (regression check): `test_finn_ad_parse` 14 OK · `test_finn_search_catalog` 10 OK ·
`test_finn_identify` 10 OK · `test_finn_cards` 12 OK → **46 tests OK**.

## Notes / limits

- Card names are kept **verbatim** (no spell-fix): cleanup/canonicalization belongs to matching (0005).
- No stated count in this ad's title/description, so `flags == []` here; the flag logic is covered by
  `Counts.test_flags_title_vs_description` (title `79 stk` vs desc `99 stk` → two explicit flags).
- The fix generalizes: any future ad containing CR/VT/FF/NEL/LS/PS gets the same consistent treatment.
