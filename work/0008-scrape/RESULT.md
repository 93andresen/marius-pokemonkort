# 0008 — Bulk-scrape the discovered FINN ads

**Status:** done
**Date:** 2026-10-08
**Owner:** code

## Goal

Actually archive the ads discovery found (the user's priority: *volume of raw data
on disk, politely paced, parse later*). The discovery registry
(`data/finn/registry/pokemon-kort.json`) is a JSON **object keyed by kode**, which
`finn_ad.py --from-jsonl` could not read — so a registry-input path was needed first.

## What was built

- `finn/finn_ad.py` → `load_registry_kodes(path)` + `--from-registry FILE`. Reads a
  registry JSON object, canonicalises each key via `finnlib.canonical_kode`, dedupes,
  returns sorted. A missing file is a **loud** `rc=2` (`ERROR: registry not found`),
  never a silent no-op.
- `tests/test_finn_ad_parse.py` → `RegistryInput` class (3 tests): load, missing-file
  returns `[]`, CLI missing-file is `rc=2` with the message.

## Evidence (verified on disk — not asserted)

- Registry loader done: **`DONE archived=106/106`** — every one of the 106 registry
  koder archived, 04:10→04:32 (~22 min), polite pacing (`--delay 1.2 --jitter 1.0`,
  `--max-images 5` to bound CDN load; raw HTML still embeds every image URL).
- `dir /b /ad data\finn\annonser` → **107** ad folders (106 new + original `475878513`).
- `find /c /v "" data\finn\_log\ad_scrapes.jsonl` → **109** append-only rows.
- `findstr` for `"status": "failed"` / `"error"` → **0**.
- Tests: `tests/test_finn_ad_parse.py` **17 OK** (14 prior + 3 new); full suite **81 OK**.

## Resume / timeout behaviour (answers to the user)

- **Timeout / kill:** nothing is lost — each ad is written to its own folder the moment
  it finishes and the log line flushes immediately; a kill costs at most the ad in flight.
- **Reboot / re-run:** it **resumes, does not start over.** `scrape_ad` calls
  `find_existing_ad_dir()` and `existing_image_for()` before writing, so archived ads
  and already-downloaded photos (matched by uuid) are skipped. Archive + logs are
  append-only.

## Follow-on

The archive→records join and the downstream identify→match→price wiring turned out to
carry two real bugs (JSONL `splitlines()` on U+2028; matcher adapter shape mismatch).
Those are item **0009**.
