#!/usr/bin/env python3
"""Regression net for ``finn/finn_corpus.py`` — join the ad archive into records.

The downstream stages (identify / match / price / tables) each read a JSONL of
records, but nothing joined the archived per-ad views into one. These tests pin
that join: deterministic order, loud-but-non-fatal problems, JSONL output.

No network, stdlib only.  Run with:

    uv run tests/test_finn_corpus.py
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "finn"))

import finn_corpus  # noqa: E402  (needs the sys.path insert above)


def make_archive(root: Path, records: dict[str, dict], *, orphan: str | None = None,
                 broken: str | None = None) -> Path:
    """Create ``annonser/<kode>_slug/<kode>.json`` folders under ``root``."""
    for kode, rec in records.items():
        folder = root / f"{kode}_slug"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{kode}.json").write_text(
            json.dumps(rec, ensure_ascii=False), encoding="utf-8"
        )
    if orphan:
        (root / f"{orphan}_slug").mkdir(parents=True, exist_ok=True)  # no view file
    if broken:
        folder = root / f"{broken}_slug"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{broken}.json").write_text("{ not json", encoding="utf-8")
    return root


class Collect(unittest.TestCase):
    def test_reads_views_sorted_and_flags_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = make_archive(
                Path(td),
                {
                    "477798898": {"finn_kode": "477798898", "title": "b"},
                    "458560266": {"finn_kode": "458560266", "title": "a"},
                },
                orphan="999999999",
            )
            records, problems = finn_corpus.collect(root)
            self.assertEqual([r["finn_kode"] for r in records],
                             ["458560266", "477798898"])
            self.assertEqual(len(problems), 1)
            self.assertIn("999999999", problems[0]["folder"])

    def test_missing_root_is_empty(self) -> None:
        records, problems = finn_corpus.collect(Path("definitely/not/here"))
        self.assertEqual(records, [])
        self.assertEqual(problems, [])

    def test_invalid_json_is_a_problem_not_a_crash(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = make_archive(Path(td), {"458560266": {"finn_kode": "458560266"}},
                                broken="477798898")
            records, problems = finn_corpus.collect(root)
            self.assertEqual(len(records), 1)
            self.assertEqual(len(problems), 1)
            self.assertIn("477798898", problems[0]["folder"])


class Build(unittest.TestCase):
    def test_cli_writes_timestamped_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = make_archive(
                Path(td) / "annonser",
                {
                    "458560266": {"finn_kode": "458560266", "title": "a"},
                    "477798898": {"finn_kode": "477798898", "title": "b"},
                },
            )
            outdir = Path(td) / "out"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = finn_corpus.main([
                    "--root", str(root), "--outdir", str(outdir),
                    "--ts", "2026-01-02-030405",
                ])
            self.assertEqual(rc, 0)
            out = outdir / "corpus_2026-01-02-030405.jsonl"
            self.assertTrue(out.is_file(), f"expected {out}")
            lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertEqual(len(lines), 2)
            # every line is one complete JSON object
            for ln in lines:
                self.assertIsInstance(json.loads(ln), dict)


if __name__ == "__main__":
    unittest.main(verbosity=2)
