#!/usr/bin/env python3
"""JSONL readers must split on ``"\\n"`` only — never ``str.splitlines()``.

Real FINN descriptions contain Unicode line/paragraph separators (U+2028/U+2029,
plus ``\\x85``, ``\\x0b``, ``\\x0c``). Our JSONL stores are written with
``ensure_ascii=False`` (finnlib.append_jsonl, finn_corpus), so those characters
appear literally inside a single JSON object. ``str.splitlines()`` wrongly treats
them as record delimiters, splitting one object into two unparseable halves —
which either crashes the reader or, in ``finn_ad._load_kodes_from``, silently
drops the kode. JSONL's delimiter is ``"\\n"``; these tests pin that.

No network, stdlib only.  Run with:

    uv run tests/test_jsonl_lines.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "finn"))

import finn_ad  # noqa: E402
import finn_identify  # noqa: E402
import finn_report  # noqa: E402

# One string holding every boundary ``str.splitlines()`` honours but JSONL must not.
BOUNDARY_TEXT = "line1\u2028line2\u2029para\x85next\x0bvert\x0cff"


class JsonlUnicodeBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = {
            "finn_kode": "458560266",
            "title": "a\u2028b",
            "description_raw": BOUNDARY_TEXT,
        }
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.tmp.name) / "rows.jsonl"
        # Exactly how the repo writes JSONL: raw (non-ASCII) + "\n" delimiter.
        cls.path.write_text(json.dumps(cls.record, ensure_ascii=False) + "\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_identify_load_rows_keeps_one_record(self) -> None:
        rows = finn_identify._load_rows(self.path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["description_raw"], BOUNDARY_TEXT)

    def test_report_read_jsonl_keeps_one_record(self) -> None:
        rows = finn_report._read_jsonl(self.path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["description_raw"], BOUNDARY_TEXT)

    def test_ad_load_kodes_from_does_not_drop_kode(self) -> None:
        kodes = finn_ad._load_kodes_from(self.path)
        self.assertEqual(kodes, ["458560266"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
