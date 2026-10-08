#!/usr/bin/env python3
"""Tests for ``finn/finn_identify.py`` (ad → interesting set/card + intent rank).

Real input is the committed capture used by the 0001 regression net; stdlib only.
Run with:  uv run tests/test_finn_identify.py
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "finn"))

import finn_ad  # noqa: E402
import finn_identify  # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "finn_ad_475878513.html"


class Normalize(unittest.TestCase):
    def test_normalize_basic(self) -> None:
        cases = [
            ("Pokémon", "pokemon"),
            ("MewTwo", "mewtwo"),
            ("  Gym  Heroes \n ✨", "gym heroes"),
            ("Ho-Oh", "ho oh"),
            ("1st. edition", "1st edition"),
        ]
        for raw, expected in cases:
            self.assertEqual(finn_identify.normalize(raw), expected, f"input={raw!r}")


class SetMatches(unittest.TestCase):
    def test_finds_sets_with_tiers(self) -> None:
        text = "Gym Heroes; Gym Challenge, Neo Destiny, Neo Revelation and 1st edition"
        m = {s["name"]: s for s in finn_identify.find_set_matches(text)}
        self.assertIn("Gym Heroes", m)
        self.assertEqual(m["Gym Heroes"]["tier"], 1)
        self.assertIn("Gym Challenge", m)
        self.assertIn("Neo Revelation", m)
        self.assertEqual(m["Neo Destiny"]["tier"], 2)
        self.assertIn("Base Set (1st Edition / Shadowless)", m)
        print(f"[sets] matched {sorted(m)}")


class CardMatches(unittest.TestCase):
    def test_word_boundary(self) -> None:
        names = {c["name"] for c in finn_identify.find_card_matches("Mew MewTwo Gengar Jolteon")}
        self.assertEqual(names, {"Mew", "Mewtwo", "Gengar", "Jolteon"})

    def test_no_substring_false_positive(self) -> None:
        names = {c["name"] for c in finn_identify.find_card_matches("mewtwo only")}
        self.assertEqual(names, {"Mewtwo"}, "the 'mew' alias must not fire inside 'mewtwo'")


class IntentRank(unittest.TestCase):
    def test_priority(self) -> None:
        tier1 = finn_identify.find_set_matches("Jungle")
        cards = finn_identify.find_card_matches("Gengar")
        tier2 = finn_identify.find_set_matches("Skyridge")
        self.assertEqual(finn_identify.intent_rank(tier1, []), 1)
        self.assertEqual(finn_identify.intent_rank([], cards), 2)
        self.assertEqual(finn_identify.intent_rank(tier2, []), 3)
        self.assertEqual(finn_identify.intent_rank([], []), 0)

    def test_tier1_beats_card(self) -> None:
        tier1 = finn_identify.find_set_matches("Fossil")
        cards = finn_identify.find_card_matches("Lugia")
        self.assertEqual(finn_identify.intent_rank(tier1, cards), 1)


class RealCaptureIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = finn_ad.parse_ad(FIXTURE.read_text(encoding="utf-8"))
        cls.res = finn_identify.identify_ad(cls.rec)

    def test_identify_real_ad(self) -> None:
        res = self.res
        print(f"[real ad] rank={res['intent_rank']} sets={res['matched_set_names']} "
              f"cards={res['matched_card_names']}")
        self.assertEqual(res["intent_rank"], 1)
        self.assertEqual(res["best_tier"], 1)
        self.assertTrue({"Gym Heroes", "Gym Challenge", "Neo Revelation"}
                        <= set(res["matched_set_names"]))
        self.assertTrue({"Mew", "Mewtwo", "Gengar", "Jolteon"}
                        <= set(res["matched_card_names"]))

    def test_annotate_does_not_mutate_input(self) -> None:
        row = {"title": "Skyridge Umbreon holo"}
        out = finn_identify.annotate(row)
        self.assertNotIn("identify", row)
        self.assertIn("identify", out)
        self.assertEqual(out["identify"]["matched_card_names"], ["Umbreon"])
        self.assertIn("Skyridge", out["identify"]["matched_set_names"])


class AnnotateRows(unittest.TestCase):
    def test_ranks_mixed_rows(self) -> None:
        rows = [
            {"heading": "Lugia Neo Genesis holo"},
            {"heading": "bare random poker cards, no pokemon terms at all"},
        ]
        ann = [finn_identify.annotate(r) for r in rows]
        self.assertEqual(ann[0]["identify"]["matched_card_names"], ["Lugia"])
        self.assertIn("Neo Genesis", ann[0]["identify"]["matched_set_names"])
        self.assertEqual(ann[0]["identify"]["intent_rank"], 1)
        self.assertEqual(ann[1]["identify"]["intent_rank"], 0)


class CliJson(unittest.TestCase):
    def test_cli_json(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = finn_identify.main(["--title", "Skyridge Umbreon holo", "--json"])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("Umbreon", data["matched_card_names"])
        self.assertIn("Skyridge", data["matched_set_names"])
        # A named card (rank 2) outranks a Tier-2 set (rank 3): both match here, so rank == 2.
        self.assertEqual(data["intent_rank"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
