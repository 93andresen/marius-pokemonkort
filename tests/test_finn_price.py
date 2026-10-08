#!/usr/bin/env python3
"""Tests for ``finn/finn_price.py`` — price an ad and each card it enumerates.

Everything here is **offline** and driven by a **seeded in-memory cache**, so the
suite makes **zero** PokeWallet calls and never touches the network.  The point
is to pin the pricing/confidence/deal contract, not to re-test the matcher.

Run with:  uv run tests/test_finn_price.py
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
sys.path.insert(0, str(REPO_ROOT / "pokewallet"))

import finn_price  # noqa: E402
from pwlib import sets as setslib  # noqa: E402
from pwlib.util import utc_iso  # noqa: E402

FX = {"USD": 10.70, "EUR": 11.60}


def make_card(pk_id: str, name: str, set_name: str, *, number: str = "4",
              tcg_market: float = 2.0, set_code: str = "BS") -> dict:
    """A minimal PokeWallet card object, shaped like a real /search result."""
    return {
        "id": pk_id,
        "card_info": {
            "name": name,
            "clean_name": name,
            "set_name": set_name,
            "set_code": set_code,
            "set_id": "604",
            "card_number": number,
            "rarity": "Common",
        },
        "tcgplayer": {
            "prices": [{"sub_type_name": "Normal", "market_price": tcg_market,
                        "low_price": 1.0, "mid_price": tcg_market}],
            "url": "https://www.tcgplayer.com/product/1",
        },
        "cardmarket": None,
    }


def seed(*pairs: tuple[str, list[dict]]) -> dict:
    """Build a ``load_cache``-shaped dict: ``normalize_name(query) -> record``."""
    cache: dict = {}
    for query, results in pairs:
        key = setslib.normalize_name(query)
        cache[key] = {
            "query": query, "query_key": key, "fetched_at": utc_iso(),
            "count": len(results), "results": results,
        }
    return cache


def ad(title: str, desc: str = "", price: float | None = None, kode: str = "999") -> dict:
    return {"finn_kode": kode, "title": title, "description_raw": desc,
            "price_nok": price}


class DealMath(unittest.TestCase):
    def test_ratio_math(self) -> None:
        d = finn_price.deal_math(200, 100)
        print(f"[deal] {d}")
        self.assertEqual(d["ratio"], 2.0)          # market / asking
        self.assertEqual(d["delta_nok"], -100)     # asking - market (deal when < 0)

    def test_ratio_none_when_no_asking(self) -> None:
        d = finn_price.deal_math(200, None)
        self.assertIsNone(d["ratio"])
        self.assertIsNone(d["delta_nok"])


class Confidence(unittest.TestCase):
    def test_levels(self) -> None:
        self.assertEqual(finn_price.confidence_of({"name_ok": False}), "none")
        self.assertEqual(
            finn_price.confidence_of({"name_ok": True, "num_ok": True, "flags": []}), "high")
        self.assertEqual(
            finn_price.confidence_of(
                {"name_ok": True, "num_ok": False, "flags": ["name_exact", "set"]}),
            "medium")
        # Exact name, no number, but the ad *did* name a set that did not match.
        self.assertEqual(
            finn_price.confidence_of(
                {"name_ok": True, "num_ok": False, "flags": ["name_exact"]},
                set_expected=True),
            "low")
        # Exact name and no set was expected -> acceptable (no red flag).
        self.assertEqual(
            finn_price.confidence_of(
                {"name_ok": True, "num_ok": False, "flags": ["name_exact"]}),
            "medium")


class Pricing(unittest.TestCase):
    def test_offline_uses_cache_no_calls(self) -> None:
        cache = seed(("Venusaur Base Set",
                      [make_card("pk1", "Venusaur", "Base Set", number="15", tcg_market=2.0)]))
        rec = ad("Pokemon kort Base Set", "Liste over kort:\n\nVenusaur", price=100)
        res = finn_price.price_ad(rec, cache=cache, offline=True, fx=FX)
        print(f"[cached] cards={res['cards']}")
        self.assertEqual(res["calls_spent"], 0)
        self.assertTrue(res["cache_hit"])
        self.assertEqual(len(res["cards"]), 1)
        row = res["cards"][0]
        self.assertTrue(row["priced"], row)
        self.assertEqual(row["confidence"], "medium")
        self.assertEqual(row["market_value_nok"], round(2.0 * FX["USD"]))
        self.assertEqual(res["deal"]["basis"], "card_list_sum")

    def test_empty_cache_is_unpriced(self) -> None:
        rec = ad("Pokemon kort Base Set", "Liste over kort:\n\nVenusaur\n\nGengar", price=100)
        res = finn_price.price_ad(rec, cache={}, offline=True, fx=FX)
        self.assertEqual(res["calls_spent"], 0)
        for row in res["cards"]:
            self.assertFalse(row["priced"])
            self.assertIsNone(row["market_value_nok"])
        self.assertIsNone(res["deal"]["market_value_nok"])
        self.assertEqual(res["deal"]["basis"], "none")

    def test_low_confidence_name_only_skipped(self) -> None:
        cache = seed(("Venusaur Base Set",
                      [make_card("pkJ", "Venusaur", "Jungle", number="15")]))
        rec = ad("Pokemon kort Base Set", "Liste over kort:\n\nVenusaur", price=100)
        res = finn_price.price_ad(rec, cache=cache, offline=True, fx=FX)
        row = res["cards"][0]
        print(f"[low] {row}")
        self.assertEqual(row["confidence"], "low")
        self.assertFalse(row["priced"])
        self.assertIsNone(row["market_value_nok"])

    def test_price_low_opt_in(self) -> None:
        cache = seed(("Venusaur Base Set",
                      [make_card("pkJ", "Venusaur", "Jungle", number="15")]))
        rec = ad("Pokemon kort Base Set", "Liste over kort:\n\nVenusaur", price=100)
        res = finn_price.price_ad(rec, cache=cache, offline=True, fx=FX, price_low=True)
        row = res["cards"][0]
        self.assertEqual(row["confidence"], "low")
        self.assertTrue(row["priced"])
        self.assertEqual(row["market_value_nok"], round(2.0 * FX["USD"]))

    def test_card_list_partial_coverage(self) -> None:
        cache = seed(("Pikachu",
                      [make_card("pkP", "Pikachu", "Base Set", number="58", tcg_market=1.0)]))
        rec = ad("Pokemon kort",
                 "Liste over kort:\n\nPikachu\n\nGengar\n\nCharizard", price=100)
        res = finn_price.price_ad(rec, cache=cache, offline=True, fx=FX)
        print(f"[coverage] {res['card_coverage']} partial={res['partial_card_coverage']}")
        self.assertEqual(res["card_coverage"]["total"], 3)
        self.assertEqual(res["card_coverage"]["priced"], 1)
        self.assertTrue(res["partial_card_coverage"])
        self.assertEqual(res["deal"]["basis"], "card_list_sum")
        self.assertEqual(res["deal"]["market_value_nok"], round(1.0 * FX["USD"]))

    def test_count_multiplier(self) -> None:
        cache = seed(("Pikachu",
                      [make_card("pkP", "Pikachu", "Base Set", number="58", tcg_market=1.0)]))
        rec = ad("Pokemon kort", "Liste over kort:\n\n4x Pikachu", price=100)
        res = finn_price.price_ad(rec, cache=cache, offline=True, fx=FX)
        row = res["cards"][0]
        unit = round(1.0 * FX["USD"])
        self.assertEqual(row["count"], 4)
        self.assertEqual(row["unit_market_value_nok"], unit)
        self.assertEqual(row["market_value_nok"], 4 * unit)
        self.assertEqual(res["deal"]["market_value_nok"], 4 * unit)

    def test_listing_best_basis(self) -> None:
        # The matcher (index=None) cannot split the trailing set, so it plans
        # "Psychic Energy Base Set 101" — seed exactly that queried key.
        cache = seed(("Psychic Energy Base Set 101",
                      [make_card("pkE", "Psychic Energy", "Base Set", number="101",
                                 tcg_market=0.67)]))
        rec = ad("Psychic Energy #101 Base Set (1999)", "", price=9)
        res = finn_price.price_ad(rec, cache=cache, offline=True, fx=FX)
        print(f"[listing] basis={res['deal']['basis']} value={res['deal']['market_value_nok']}")
        self.assertEqual(res["cards"], [])
        self.assertEqual(res["deal"]["basis"], "listing_best")
        self.assertEqual(res["deal"]["market_value_nok"], round(0.67 * FX["USD"]))


class Cli(unittest.TestCase):
    def test_cli_offline_json(self) -> None:
        caps = sorted((REPO_ROOT / "data" / "finn" / "annonser").glob(
            "475878513_*/475878513.json"))
        if not caps:
            self.skipTest("real ad capture missing")
        cache_file = REPO_ROOT / "data" / "finn" / "_cache" / "query_cache.jsonl"
        tmp = tempfile.mkdtemp(prefix="finn_price_cli_")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = finn_price.main([
                "--ad-json", str(caps[0]), "--offline",
                "--cache-file", str(cache_file),
                "--max-cards", "3", "--outdir", tmp, "--json",
            ])
        self.assertEqual(rc, 0, buf.getvalue())
        data = json.loads(buf.getvalue())
        self.assertIsInstance(data, list)
        item = data[0]
        self.assertIn("deal", item)
        self.assertIn("cards", item)
        self.assertEqual(item["calls_spent"], 0)
        self.assertLessEqual(len(item["cards"]), 3)
        self.assertTrue((Path(tmp) / "pricing.jsonl").exists(),
                        "append-only pricing.jsonl was not written")


if __name__ == "__main__":
    unittest.main(verbosity=2)
