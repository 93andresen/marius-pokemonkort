# TASK 0008 — Bulk-scrape the discovered ads into the archive

- **Status:** in-progress
- **Owner:** Zoo (code mode)
- **Output artifact(s):** `finn/finn_ad.py` (add `--from-registry`), `tests/test_finn_ad_parse.py` (new
  registry cases), and the resulting real archive under `data/finn/annonser/`
- **Depends on:** 0002 (`finn_search.py` → `data/finn/registry/pokemon-kort.json`, 106 koder), `finn_ad.py`
- **Reuses (does NOT re-hard-code):** `finn_ad.scrape_ad` (raw capture + parse + images + manifest +
  append-only log), `finnlib.canonical_kode`/`ITEM_URL_TMPL`, the existing resumable/idempotent archive path

## Goal (one sentence)

Actually **run the scraper against every FINN-kode the discovery stage found** — not just build machinery —
archiving raw HTML, parsed JSON and photos for as many ads as possible, paced politely so finn.no does not
ban us; parsing / pricing / tabling come later.

## Why / context

The user's explicit, most-recent instruction:

> *"be careful so we don't get baned by finn.no i dont need it to run fast i need it to run alot! Now keep
> scraping we need as many as possible! then we can figure out how to parse the data once we actually have
> all the data on disk! take your time but start the actual scraping!"*

State before this item: **106 koder discovered** but only **1 ad archived** (`475878513`). The pipeline was
built and tested end-to-end, but never driven over the discovered set. This item closes that gap.

Priority is **volume of raw data on disk**, not speed, and **politeness** (base delay + jitter between every
request; the module already spaces image downloads too).

## In scope

- A tiny, tested input path so the archive can be driven straight from the discovery registry: add
  `load_registry_kodes(path)` + a `--from-registry FILE` CLI flag to `finn/finn_ad.py` (the registry is a
  JSON *object* keyed by kode, which the existing `--from-jsonl` cannot read).
- Run `uv run finn/finn_ad.py --from-registry data/finn/registry/pokemon-kort.json` over all 106 koder, with
  images, using a politeness margin (delay + jitter).
- Capture real evidence: archived folder count, `data/finn/_log/ad_scrapes.jsonl` rows, failures surfaced.

## Out of scope (do NOT touch)

- Re-running the search / discovery stage (registry already exists).
- Parsing / matching / pricing / tables / report over the bigger archive (user: "then we can figure out how
  to parse the data").
- Any change to the archive layout or to how an individual ad is parsed.

## Success criteria (DEFINE THESE YOURSELF, before coding)

- [ ] `load_registry_kodes` returns each registry key as a canonical kode, de-duplicated, deterministically
      ordered, silently ignoring non-kode keys; a missing file returns `[]`.
- [ ] `finn_ad.main(["--from-registry", <missing>])` fails loudly with rc 2 (never a silent no-op).
- [ ] The scrape archives **substantially more than 1** ad; every attempt is recorded in
      `data/finn/_log/ad_scrapes.jsonl` (success row **or** an explicit error row — no silent drops).
- [ ] Every archived ad has `raw/*.html`, `parsed/*.json`, a `<kode>.json` view and a `manifest.json`.
- [ ] Re-running is safe: existing ads are reused (no overwrite); raw captures get fresh timestamped names.
- [ ] Full stdlib suite stays green (existing 78 + new registry tests).

## Test plan (write these tests FIRST — under `tests/`, stdlib, temp dir)

| Test | Input | Expected |
|---|---|---|
| `test_load_registry_kodes` | tmp registry JSON with 3 koder + 1 noise key | 3 canonical koder, sorted, deduped |
| `test_load_registry_kodes_missing_file` | path that does not exist | `[]` |
| `test_cli_from_registry_missing_is_error` | `main(["--from-registry", missing])` | rc 2 (loud), no network |

## Evidence to capture

- `uv run tests/test_finn_ad_parse.py` (count + OK) and full-suite tally.
- The live bulk run: `DONE archived=N/M`, plus the on-disk count of `data/finn/annonser/*/`.
- `type data/finn/_log/ad_scrapes.jsonl` tail + a `type` of one freshly archived `<kode>.json`.

## Open questions / assumptions

- The registry may include ads that have since gone (status `Solgt`/`Inaktiv`) — those are **kept**: status is
  as valuable as price, and the archive is append-only. Every kode is attempted.
- Politeness margin: keep the default small delay but raise it a little, since the brief prioritises volume
  over speed and avoiding a ban.
