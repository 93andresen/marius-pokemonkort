#!/usr/bin/env python3
"""Tests for the FINN tab builder in ``sheet/build_sheet.py``.

The FINN tab used to be a stub (``"rows": []``) so the sheet never carried any
FINN data.  ``build_finn`` now assembles the tab from the real artifacts:

* the archive (``data/finn/annonser/<kode>_<slug>/<kode>.json``) is the row
  universe — one row per archived ad (via ``finn_corpus.collect``);
* the registry gives ``first_seen`` / ``last_seen``;
* the newest pricing record per kode gives the matched card + market value +
  delta + ratio.

Everything is offline and driven by temp files.  Missing artifacts must yield
blank cells, never a crash and never a fabricated ``0``.

Run with:  uv run tests/test_build_sheet_finn.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "sheet"))
sys.path.insert(0, str(REPO_ROOT / "finn"))

import build_sheet  # noqa: E402


def _write_ad(root: Path, kode: str, slug: str, **view) -> None:
    folder = root / f"{kode}_{slug}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{kode}.json").write_text(
        json.dumps({"finn_kode": kode, **view}, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8")


class BuildFinn(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.td = Path(self._td.name)
        self.annonser = self.td / "annonser"
        _write_ad(self.annonser, "111111111", "alpha",
                  title="Alpha", price_nok=100, status="Aktiv", url="u1")
        _write_ad(self.annonser, "222222222", "beta",
                  title="Beta", price_nok=500, status="Inaktiv", url="u2")

        self.registry = self.td / "pokemon-kort.json"
        self.registry.write_text(json.dumps({
            "111111111": {"first_seen": "2026-01-01T00:00:00Z",
                          "last_seen": "2026-01-05T00:00:00Z",
                          "last_price": 100, "heading": "Alpha"},
        }), encoding="utf-8")

        self.pricing = self.td / "pricing.jsonl"
        _write_jsonl(self.pricing, [
            {"finn_kode": "111111111", "heading": "Alpha",
             "deal": {"market_value_nok": 300, "asking_price_nok": 100,
                      "delta_nok": -200, "ratio": 3.0, "basis": "card_list_sum"},
             "listing": {"best": {"name": "Pikachu"}}},
            # newer record for the same kode must win (append-only → last is truth)
            {"finn_kode": "111111111", "heading": "Alpha",
             "deal": {"market_value_nok": 250, "asking_price_nok": 100,
                      "delta_nok": -150, "ratio": 2.5, "basis": "card_list_sum"},
             "listing": {"best": {"name": "Pikachu"}}},
        ])
        self.matches = self.td / "matches.jsonl"
        _write_jsonl(self.matches, [])

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_rows_cover_every_archived_ad(self) -> None:
        rows = build_sheet.build_finn(self.annonser, self.registry,
                                      self.pricing, self.matches)
        self.assertEqual(len(rows), 2)
        self.assertEqual({r[0] for r in rows}, {"111111111", "222222222"})

    def test_best_deal_first_then_blanks(self) -> None:
        rows = build_sheet.build_finn(self.annonser, self.registry,
                                      self.pricing, self.matches)
        # the priced deal (ratio present) sorts before the unpriced ad
        self.assertEqual(rows[0][0], "111111111")
        self.assertEqual(rows[-1][0], "222222222")

    def test_priced_row_uses_newest_record_and_registry_dates(self) -> None:
        rows = build_sheet.build_finn(self.annonser, self.registry,
                                      self.pricing, self.matches)
        row = next(r for r in rows if r[0] == "111111111")
        self.assertEqual(row[1], "Alpha")          # title
        self.assertEqual(row[2], 100)              # asking price
        self.assertEqual(row[3], "Pikachu")        # matched card
        self.assertEqual(row[4], 250)              # newest market value (not 300)
        self.assertEqual(row[5], -150)             # delta
        self.assertEqual(row[6], 2.5)              # ratio
        self.assertEqual(row[7], "Aktiv")          # status
        self.assertEqual(row[8], "2026-01-01T00:00:00Z")  # first seen (registry)
        self.assertEqual(row[9], "2026-01-05T00:00:00Z")  # last seen (registry)

    def test_unpriced_row_has_blank_market_not_zero(self) -> None:
        rows = build_sheet.build_finn(self.annonser, self.registry,
                                      self.pricing, self.matches)
        row = next(r for r in rows if r[0] == "222222222")
        self.assertEqual(row[1], "Beta")
        self.assertEqual(row[2], 500)
        self.assertEqual(row[3], "")   # no matched card
        self.assertEqual(row[4], "")   # market blank, never 0
        self.assertEqual(row[5], "")
        self.assertEqual(row[6], "")
        self.assertEqual(row[7], "Inaktiv")
        self.assertEqual(row[8], "")   # not in registry
        self.assertEqual(row[9], "")

    def test_header_matches_row_width(self) -> None:
        rows = build_sheet.build_finn(self.annonser, self.registry,
                                      self.pricing, self.matches)
        self.assertEqual(len(build_sheet.FINN_HEADER), 10)
        for r in rows:
            self.assertEqual(len(r), len(build_sheet.FINN_HEADER))

    def test_missing_artifacts_are_empty_not_crash(self) -> None:
        rows = build_sheet.build_finn(self.td / "nope", self.td / "nope.json",
                                      self.td / "nope.jsonl", self.td / "nope.jsonl")
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
