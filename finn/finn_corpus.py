#!/usr/bin/env python3
"""Join the ad archive into one records JSONL (the downstream stages' input).

The ad archive (``data/finn/annonser/``) stores one folder per FINN-kode holding
a latest ``<kode>.json`` "view". Every downstream stage — ``finn_identify`` /
``finn_matcher`` / ``finn_price`` / ``finn_tables`` / ``finn_report`` — reads a
**JSONL of records**, but nothing joined the archive into one stream. This module
does exactly that, read-only over the archive and deterministic (sorted by kode):

  uv run finn/finn_corpus.py                         # -> data/finn/matches/corpus_<ts>.jsonl
  uv run finn/finn_corpus.py --outdir <DIR>          # choose the output dir
  uv run finn/finn_corpus.py --json                  # print a summary as JSON

A folder without a readable ``<kode>.json`` is reported as a *problem* (loudly)
but never crashes the join — the archive is append-only and a half-written ad
must not take down the whole run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import finnlib as fl  # noqa: E402  (local sibling module)

CORPUS_VERSION = "finn_corpus/1.0.0"
DATA_FINN = fl.DATA_FINN
DEFAULT_ROOT = DATA_FINN / "annonser"
DEFAULT_OUTDIR = DATA_FINN / "matches"


def ad_view_path(folder: Path) -> Path:
    """Return the ``<kode>.json`` view path for an ``<kode>_<slug>`` folder."""
    kode = folder.name.split("_", 1)[0]
    return folder / f"{kode}.json"


def collect(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Return ``(records, problems)`` for every ad folder under ``root``.

    Records are the parsed ad views, ordered by ``finn_kode``. A folder whose view
    is missing / unreadable / not a JSON object is recorded in ``problems`` (with
    the folder name and the reason) and skipped — never a silent drop, never a
    crash.
    """
    records: list[dict[str, Any]] = []
    problems: list[dict[str, str]] = []
    if not root.is_dir():
        return records, problems
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        view = ad_view_path(folder)
        if not view.is_file():
            problems.append({"folder": folder.name, "error": f"no view file {view.name!r}"})
            continue
        try:
            rec = json.loads(view.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - report, do not crash the join
            problems.append({"folder": folder.name, "error": f"unreadable json: {exc!r}"})
            continue
        if not isinstance(rec, dict):
            problems.append({"folder": folder.name, "error": "view is not a JSON object"})
            continue
        records.append(rec)
    records.sort(key=lambda r: str(r.get("finn_kode") or ""))
    return records, problems


def build(root: Path, outdir: Path, *, ts: str | None = None) -> dict[str, Any]:
    """Write ``corpus_<ts>.jsonl`` (one ad view per line) and return a summary."""
    records, problems = collect(root)
    outdir = fl.ensure_dir(outdir)
    ts = ts or fl.ts_now()
    out = fl.unique_path(outdir / f"corpus_{ts}.jsonl")
    with out.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False))
            fh.write("\n")
    return {
        "corpus_version": CORPUS_VERSION,
        "generated_at": fl.iso_now(),
        "root": str(root),
        "out": str(out),
        "records": len(records),
        "problems": problems,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", default=str(DEFAULT_ROOT),
                        help="ad archive root (default data/finn/annonser)")
    parser.add_argument("--outdir", default=str(DEFAULT_OUTDIR),
                        help="where to write corpus_<ts>.jsonl (default data/finn/matches)")
    parser.add_argument("--ts", help="force the timestamp (default: now)")
    parser.add_argument("--json", action="store_true", help="print the summary as JSON")
    args = parser.parse_args(argv)

    summary = build(Path(args.root), Path(args.outdir), ts=args.ts)

    if summary["json"] if False else args.json:  # keep --json deterministic
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"records = {summary['records']}  problems = {len(summary['problems'])}")
        for p in summary["problems"]:
            print(f"  PROBLEM {p['folder']}: {p['error']}")
        print(f"corpus -> {summary['out']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
