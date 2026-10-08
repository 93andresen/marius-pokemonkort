#!/usr/bin/env python3
"""Tests for ``finn/finn_cards.py`` (structure enumerated card lists + provenance + flags).

Real input is the committed capture from the 0001 regression net; stdlib only.
Run with:  uv run tests/test_finn_cards.py
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

import finn_ad  # noqa: E402
import finn_cards  # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "finn_ad_475878513.html"


class RealCapture(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = finn_ad.parse_ad(FIXTURE.read_text(encoding="utf-8"))
        cls.desc = cls.rec["description_raw"]
        cls.res = finn_cards.structure(cls.rec)
        print(f"[real] present={cls.res['card_list_present']} marker={cls.res['marker']!r} "
              f"lines={cls.res['card_line_count']} total={cls.res['card_count']} "
              f"flags={cls.res['flags']}")

    def test_real_capture_block(self) -> None:
        self.assertTrue(self.res["card_list_present"])
        self.assertIn("liste over kort", self.res["marker"].lower())
        names = {c["name"].casefold() for c in self.res["cards"]}
        self.assertTrue({"venusaur", "mew", "mewtwo", "gengar", "jolteon"} <= names)
        self.assertGreaterEqual(self.res["card_line_count"], 40)

    def test_line_index_is_global(self) -> None:
        # Provenance must be expressed in the module's canonical line space,
        # which normalizes every Unicode line boundary (LS/PS/CR/...) to "\n".
        lines = finn_cards.logical_lines(self.desc)
        for c in self.res["cards"]:
            self.assertLess(c["line_index"], len(lines),
                            f"index out of range for {c['name']!r}")
            self.assertEqual(lines[c["line_index"]].strip(), c["raw"].strip(),
                             f"provenance wrong for {c['name']!r}")


class LineParsing(unittest.TestCase):
    def test_counts_per_line(self) -> None:
        self.assertEqual(finn_cards.parse_card_line("4x Pikachu", 0)["count"], 4)
        self.assertEqual(finn_cards.parse_card_line("Pikachu x3", 0)["count"], 3)
        self.assertEqual(finn_cards.parse_card_line("Charizard", 0)["count"], 1)

    def test_variants(self) -> None:
        c1 = finn_cards.parse_card_line("Charizard reverse holo", 0)
        self.assertEqual(c1["name"], "Charizard")
        self.assertIn("reverse holo", c1["variants"])
        c2 = finn_cards.parse_card_line("Mew holo", 0)
        self.assertEqual(c2["name"], "Mew")
        self.assertIn("holo", c2["variants"])
        c3 = finn_cards.parse_card_line("Blastoise 1st edition", 0)
        self.assertEqual(c3["name"], "Blastoise")
        self.assertIn("1st edition", c3["variants"])

    def test_count_only_line_is_not_a_card(self) -> None:
        self.assertIsNone(finn_cards.parse_card_line("99 stk", 0))
        self.assertIsNone(finn_cards.parse_card_line("534 kort", 0))
        self.assertIsNone(finn_cards.parse_card_line("42", 0))


class LogicalLines(unittest.TestCase):
    def test_normalizes_unicode_boundaries(self) -> None:
        # U+2028/CR/VT must become "\n" so an index can never drift against
        # the "\n"-count that computes line_index (the real-capture bug).
        self.assertEqual(finn_cards.logical_lines("a\u2028b\rc\x0bd"), ["a", "b", "c", "d"])
        self.assertEqual(finn_cards.logical_lines("a\r\nb"), ["a", "b"])
        self.assertEqual(finn_cards.logical_lines("a\nb"), ["a", "b"])


class BlockDetection(unittest.TestCase):
    def test_no_list(self) -> None:
        res = finn_cards.structure({"description_raw": "Bare a normal ad with no card list."})
        self.assertFalse(res["card_list_present"])
        self.assertEqual(res["cards"], [])

    def test_bulleted_list_without_marker(self) -> None:
        names = ["Pikachu", "Gengar", "Mew", "Mewtwo", "Lugia",
                 "Umbreon", "Rayquaza", "Jolteon", "Alakazam"]
        desc = "\n".join(f"- {n}" for n in names)
        res = finn_cards.parse_card_list(desc)
        self.assertTrue(res["card_list_present"])
        self.assertEqual(res["marker"], "(bullet/numbered run)")
        self.assertEqual(res["card_line_count"], len(names))

    def test_stop_boilerplate(self) -> None:
        desc = "Liste over kort:\n\nPikachu\n\nGengar\n\nSendes i toploader med sleeve"
        res = finn_cards.parse_card_list(desc)
        names = {c["name"] for c in res["cards"]}
        self.assertIn("Pikachu", names)
        self.assertIn("Gengar", names)
        self.assertTrue(all("Sendes" not in c["raw"] for c in res["cards"]))


class Counts(unittest.TestCase):
    def test_extract_counts(self) -> None:
        self.assertEqual(finn_cards.extract_counts("79 stk Pokemon kort"), [79])
        self.assertEqual(finn_cards.extract_counts("260+ kort"), [260])
        self.assertEqual(finn_cards.extract_counts("534 stk"), [534])
        self.assertEqual(finn_cards.extract_counts("pris 100 kr"), [])

    def test_flags_title_vs_description(self) -> None:
        desc = "Liste over kort:\n\nPikachu\n\nGengar\n\nCharizard\n\nLugia\n\n99 stk"
        res = finn_cards.structure({"title": "79 stk Pokemon kort", "description_raw": desc})
        print(f"[flags] {res['flags']}")
        self.assertTrue(any("79" in f and "99" in f for f in res["flags"]),
                        f"expected a 79-vs-99 flag, got {res['flags']}")
        self.assertTrue(any("title states 79" in f for f in res["flags"]))


class Cli(unittest.TestCase):
    def test_cli_json_from_file(self) -> None:
        desc = "Liste over kort:\n\nPikachu\n\nGengar\n\nCharizard\n\nLugia\n\nMew\n\nMewtwo\n\nJolteon"
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
            fh.write(desc)
            path = fh.name
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = finn_cards.main(["--title", "Pokemon kort", "--file", path])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertTrue(data["card_list_present"])
        self.assertEqual(data["card_line_count"], 7)
        Path(path).unlink()


if __name__ == "__main__":
    unittest.main(verbosity=2)
