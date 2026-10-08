#!/usr/bin/env python3
"""Tests for ``finn/finn_report.py`` — count what actually flowed through the pipeline.

Everything here is **pure accounting** over tiny temp fixtures: no network, no
scraping, no pricing.  The point is to pin the coverage counts and the
missing-artifact behaviour (zeros, never a crash).

Run with:  uv run tests/test_finn_report.py
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

import finn_report as fr  # noqa: E402


# --- fixture builders ------------------------------------------------------ #


def write_json(path: Path, obj: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")
    return path


def write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def registry() -> dict:
    return {
        "111": {"first_seen": "2026-10-02T16:00:00Z", "last_seen": "2026-10-08T02:00:00Z",
                "last_price": 100, "heading": "A"},
        "222": {"first_seen": "2026-10-05T16:00:00Z", "last_seen": "2026-10-05T16:00:00Z",
                "last_price": 0, "heading": "B"},
    }


# --- registry -------------------------------------------------------------- #


class Registry(unittest.TestCase):
    def test_count_registry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = write_json(Path(td) / "reg.json", registry())
            cov = fr.count_registry(p)
        self.assertEqual(cov["koder"], 2)
        self.assertEqual(cov["first_seen"], "2026-10-02T16:00:00Z")
        self.assertEqual(cov["last_seen"], "2026-10-08T02:00:00Z")

    def test_missing_artifact_is_zero(self) -> None:
        cov = fr.count_registry(Path("does/not/exist.json"))
        self.assertEqual(cov["koder"], 0)
        self.assertTrue(cov["notes"])


# --- search runs ----------------------------------------------------------- #


class Runs(unittest.TestCase):
    def test_count_runs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_json(base / "r1" / "run.json", {"totals": {"pages": 2, "docs": 53}})
            write_json(base / "r2" / "run.json", {"totals": {"pages": 3, "docs": 100}})
            cov = fr.count_runs(base)
        self.assertEqual(cov["runs"], 2)
        self.assertEqual(cov["pages"], 5)
        self.assertEqual(cov["docs"], 153)


# --- matches --------------------------------------------------------------- #


class Matches(unittest.TestCase):
    def test_count_matches(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = write_jsonl(Path(td) / "m.jsonl", [
                {"finn_kode": "a", "best": {"pk_id": "x"}},
                {"finn_kode": "b", "best": None},
            ])
            cov = fr.count_matches(p)
        self.assertEqual(cov["records"], 2)
        self.assertEqual(cov["matched"], 1)


# --- pricing --------------------------------------------------------------- #


class Pricing(unittest.TestCase):
    def test_count_pricing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = write_jsonl(Path(td) / "p.jsonl", [
                {"deal": {"market_value_nok": 200, "ratio": 2.0, "basis": "card_list_sum"},
                 "card_coverage": {"total": 3, "priced": 2}},
                {"deal": {"market_value_nok": None, "ratio": None, "basis": "none"},
                 "card_coverage": {"total": 5, "priced": 0}},
            ])
            cov = fr.count_pricing(p)
        self.assertEqual(cov["records"], 2)
        self.assertEqual(cov["with_value"], 1)
        self.assertEqual(cov["with_ratio"], 1)
        self.assertEqual(cov["basis"], {"card_list_sum": 1, "none": 1})
        self.assertEqual(cov["cards_total"], 8)
        self.assertEqual(cov["cards_priced"], 2)


# --- archive --------------------------------------------------------------- #


class Archive(unittest.TestCase):
    def test_count_archive(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "111_a").mkdir()
            (base / "222_b").mkdir()
            cov = fr.count_archive(base)
        self.assertEqual(cov["ads"], 2)

    def test_archive_missing_is_zero(self) -> None:
        cov = fr.count_archive(Path("nope-dir"))
        self.assertEqual(cov["ads"], 0)


# --- intent distribution --------------------------------------------------- #


class Intent(unittest.TestCase):
    def test_intent_distribution_dedupes(self) -> None:
        ads = [
            {"finn_kode": "a", "heading": "Charizard Base Set", "description_raw": ""},
            {"finn_kode": "a", "heading": "Charizard Base Set", "description_raw": ""},
            {"finn_kode": "b", "heading": "Vintage lot", "description_raw": ""},
        ]
        dist = fr.intent_distribution(ads)
        self.assertEqual(dist.pop("total"), 2)
        self.assertEqual(sum(dist.values()), 2)


# --- composition + markdown + CLI ------------------------------------------ #


class Build(unittest.TestCase):
    def _fixtures(self, base: Path) -> dict:
        return {
            "registry": write_json(base / "registry" / "pokemon-kort.json", registry()),
            "searches_dir": base / "searches",
            "matches": write_jsonl(base / "matches" / "matches.jsonl",
                                   [{"finn_kode": "a", "best": {"pk_id": "x"}}]),
            "pricing": write_jsonl(base / "matches" / "pricing.jsonl",
                                   [{"deal": {"market_value_nok": 200, "ratio": 2.0,
                                              "basis": "card_list_sum"},
                                     "card_coverage": {"total": 3, "priced": 2}}]),
            "annonser": base / "annonser",
        }

    def test_coverage_and_render_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            fx = self._fixtures(base)
            write_json(fx["searches_dir"] / "r1" / "run.json", {"totals": {"pages": 1, "docs": 53}})
            write_jsonl(fx["searches_dir"] / "r1" / "all_ads.jsonl",
                        [{"finn_kode": "a", "heading": "Charizard Base Set", "description_raw": ""}])
            fx["annonser"].mkdir()
            (fx["annonser"] / "111_a").mkdir()
            cov = fr.coverage(**fx)
            md = fr.render_markdown(cov)
        self.assertEqual(cov["discovery"]["koder"], 2)
        self.assertEqual(cov["pricing"]["with_ratio"], 1)
        for section in ("Discovery", "Archive", "Identify", "Match", "Pricing"):
            self.assertIn(section, md)

    def test_cli_writes_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            fx = self._fixtures(base)
            out = base / "reports"
            buf, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                rc = fr.main([
                    "--registry", str(fx["registry"]),
                    "--searches-dir", str(fx["searches_dir"]),
                    "--matches", str(fx["matches"]),
                    "--pricing", str(fx["pricing"]),
                    "--annonser", str(fx["annonser"]),
                    "--outdir", str(out),
                    "--ts", "2026-01-02-030405",
                    "--json",
                ])
            self.assertEqual(rc, 0)
            names = sorted(p.name for p in out.iterdir())
            self.assertEqual(names, [
                "coverage_2026-01-02-030405.json",
                "coverage_2026-01-02-030405.md",
            ])
            self.assertEqual(json.loads(buf.getvalue())["discovery"]["koder"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
