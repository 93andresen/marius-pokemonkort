#!/usr/bin/env python3
"""Tests for ``finn/finn_deals.py`` — the comprehensive per-ad deal table.

Everything here is pure (no network, no API): the module joins the **ad archive**
shape, the **identify** labels, and the **pricing.jsonl** record shape into one
deduplicated row per ad. The fixtures are hand-built to exercise dedupe-by-best,
identity projection, card-list confidence, intent-first ordering, the Sheet column
mapping, priority ordering, and the timestamped outputs.

Run with:  uv run tests/test_finn_deals.py
"""
from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "finn"))

import finn_deals as fd  # noqa: E402


# --- fixtures -------------------------------------------------------------- #


def ad(kode: str, title: str, price: float = 100.0, *, status: str = "Aktiv",
       desc: str = "", **extra) -> dict:
    """One archived ad-view record (the shape ``finn_corpus.collect`` yields)."""
    return {
        "finn_kode": kode, "title": title, "url": f"https://www.finn.no/{kode}",
        "price_nok": price, "status": status, "location_text": "Oslo",
        "gallery_count": 3, "image_uuids": ["a", "b", "c"],
        "last_modified": "2026-10-08T00:00:00", "description_raw": desc, **extra,
    }


def card(name: str, *, confidence: str = "high", priced: bool = True,
         unit: float = 5.0, count: int = 1) -> dict:
    return {
        "name": name, "count": count, "variants": [], "query": name,
        "confidence": confidence, "pk_name": name, "pk_set_name": "Base Set",
        "pk_card_number": "4", "priced": priced,
        "unit_market_value_nok": unit, "market_value_nok": unit * count if priced else None,
    }


def pricing_rec(kode: str, *, market: float | None = None, ratio: float | None = None,
                delta: float | None = None, basis: str = "listing_best",
                conf: str = "high", cards: list[dict] | None = None,
                flags: list[str] | None = None, generated: str = "2026-10-08T05:00:00Z",
                partial: bool = False, best: dict | None = None) -> dict:
    """A minimal ``finn_price.price_ad`` output record."""
    cards = cards or []
    priced = sum(1 for c in cards if c.get("priced"))
    return {
        "price_version": "finn_price/1.0.0", "generated_at": generated,
        "finn_kode": kode,
        "deal": {"basis": basis, "asking_price_nok": 100.0,
                 "market_value_nok": market, "delta_nok": delta, "ratio": ratio},
        "listing_confidence": conf,
        "partial_card_coverage": partial,
        "cards": cards,
        "card_coverage": {"total": len(cards), "priced": priced},
        "flags": flags or [],
        "listing": {"best": best if best is not None else
                    ({"name": "Charizard", "set_name": "Base Set", "card_number": "4"}
                     if market is not None else None)},
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


# --- dedupe ----------------------------------------------------------------- #


class TestLatestPricing(unittest.TestCase):
    def test_prefers_record_with_a_value_over_newer_empty(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "pricing.jsonl"
            write_jsonl(p, [
                pricing_rec("111", market=None, ratio=None, generated="2026-10-09T00:00:00Z"),
                pricing_rec("111", market=250.0, ratio=2.5, generated="2026-10-08T00:00:00Z"),
            ])
            best = fd.latest_pricing(p)
            self.assertEqual(len(best), 1, "one ad -> one record")
            self.assertEqual(best["111"]["deal"]["market_value_nok"], 250.0,
                             "a valued record must beat a newer empty one")
            print(f"dedupe: kept market={best['111']['deal']['market_value_nok']}")

    def test_prefers_more_priced_cards_then_newest(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "pricing.jsonl"
            write_jsonl(p, [
                pricing_rec("222", market=10.0, ratio=0.1, cards=[card("A")],
                            generated="2026-10-09T00:00:00Z"),
                pricing_rec("222", market=10.0, ratio=0.1,
                            cards=[card("A"), card("B")],
                            generated="2026-10-08T00:00:00Z"),
            ])
            best = fd.latest_pricing(p)
            self.assertEqual(best["222"]["card_coverage"]["priced"], 2,
                             "more priced cards wins when both have a value")

    def test_skips_records_without_a_kode(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "pricing.jsonl"
            write_jsonl(p, [
                pricing_rec("", market=1.0, ratio=0.1),           # heading-only probe
                pricing_rec("333", market=99.0, ratio=0.99),
            ])
            best = fd.latest_pricing(p)
            self.assertEqual(list(best), ["333"],
                             "heading-only records (no kode) are not ads")

    def test_missing_file_is_empty(self):
        self.assertEqual(fd.latest_pricing(Path("does_not_exist_xyz.jsonl")), {})


# --- rows ------------------------------------------------------------------- #


class TestBuildRows(unittest.TestCase):
    def test_one_row_per_ad_with_archive_identity(self):
        records = [ad("111", "Charizard Base Set 4/102"),
                   ad("222", "Umbreon Gold Star")]
        rows = fd.build_rows(records, {})
        self.assertEqual(len(rows), 2)
        r = rows[0]
        self.assertEqual(r["finn_kode"], "111")
        self.assertEqual(r["title"], "Charizard Base Set 4/102")
        self.assertEqual(r["status"], "Aktiv")
        self.assertEqual(r["location"], "Oslo")
        self.assertEqual(r["images"], 3)
        # No pricing -> missing numbers are None (blank), never a fake 0.
        self.assertIsNone(r["market_value_nok"])
        self.assertIsNone(r["ratio"])
        self.assertEqual(r["confidence"], "none")
        print(f"row: kode={r['finn_kode']} intent={r['intent']} market={r['market_value_nok']}")

    def test_listing_match_fills_card_and_confidence(self):
        records = [ad("111", "Charizard Base Set 4/102")]
        pricing = {"111": pricing_rec("111", market=1500.0, ratio=1.5, delta=-1400.0)}
        row = fd.build_rows(records, pricing)[0]
        self.assertEqual(row["pk_card"], "Charizard")
        self.assertEqual(row["pk_set"], "Base Set")
        self.assertEqual(row["pk_number"], "4")
        self.assertEqual(row["market_value_nok"], 1500.0)
        self.assertEqual(row["ratio"], 1.5)
        self.assertEqual(row["confidence"], "high")

    def test_card_list_sum_joins_distinct_cards_and_derives_confidence(self):
        records = [ad("475878513", "Stort vintage salg",
                      desc="Liste over kort:\n1x Charizard\n1x Blastoise")]
        rec = pricing_rec(
            "475878513", market=300.0, ratio=3.0, basis="card_list_sum",
            cards=[card("Charizard", confidence="high"),
                   card("Blastoise", confidence="high")],
            partial=True, flags=["card list only partially priced (2/3)"])
        row = fd.build_rows(records, {"475878513": rec})[0]
        self.assertIn("Charizard", row["pk_card"])
        self.assertIn("Blastoise", row["pk_card"])
        self.assertEqual(row["coverage"], "2/2")
        self.assertEqual(row["confidence"], "high", "all-high cards -> high")
        self.assertTrue(row["partial"])
        self.assertIn("partially priced", row["notes"])

    def test_card_confidence_majority_low(self):
        rec = pricing_rec("1", market=1.0, ratio=0.1, basis="card_list_sum",
                          cards=[card("A", confidence="high"),
                                 card("B", confidence="low"),
                                 card("C", confidence="low"),
                                 card("D", confidence="low")])
        self.assertEqual(fd.card_confidence(rec), "low")


class TestCardConfidenceEdges(unittest.TestCase):
    def test_none_when_nothing_priced(self):
        rec = pricing_rec("1", cards=[card("A", priced=False)])
        self.assertIsNone(fd.card_confidence(rec))
        self.assertEqual(fd.row_confidence(None), "none")


# --- ordering --------------------------------------------------------------- #


class TestSortRows(unittest.TestCase):
    def test_intent_first_then_ratio_desc(self):
        rows = [
            {"finn_kode": "n1", "intent_rank": 0, "ratio": 9.0},
            {"finn_kode": "t1", "intent_rank": 1, "ratio": 1.2},
            {"finn_kode": "t1b", "intent_rank": 1, "ratio": 4.0},
            {"finn_kode": "c2", "intent_rank": 2, "ratio": None},
        ]
        ordered = [r["finn_kode"] for r in fd.sort_rows(rows)]
        self.assertEqual(ordered, ["t1b", "t1", "c2", "n1"],
                         "Tier-1 first (best ratio first), then named, then none")

    def test_missing_ratio_sorts_after_present_within_intent(self):
        rows = [
            {"finn_kode": "a", "intent_rank": 1, "ratio": None},
            {"finn_kode": "b", "intent_rank": 1, "ratio": 0.5},
        ]
        self.assertEqual([r["finn_kode"] for r in fd.sort_rows(rows)], ["b", "a"])


# --- sheet mapping ---------------------------------------------------------- #


class TestSheetRows(unittest.TestCase):
    def test_maps_to_the_ten_sheet_columns(self):
        rows = [{
            "finn_kode": "111", "title": "Charizard", "asking_price_nok": 100.0,
            "pk_card": "Charizard", "pk_set": "Base Set", "market_value_nok": 1500.0,
            "delta_nok": -1400.0, "ratio": 15.0, "status": "Aktiv",
            "first_seen": "2026-10-02T00:00:00Z", "last_seen": "2026-10-08T00:00:00Z",
        }]
        out = fd.sheet_rows(rows)
        self.assertEqual(len(out[0]), len(fd.SHEET_COLUMNS))
        self.assertEqual(out[0][0], "111")
        self.assertEqual(out[0][3], "Charizard (Base Set)")
        self.assertEqual(out[0][4], 1500.0)


# --- priority + build ------------------------------------------------------- #


class TestPriority(unittest.TestCase):
    def test_tier1_then_named_then_tier2_then_rest(self):
        records = [
            ad("d", "bare random kort"),                       # none
            ad("c", "Skyridge holo"),                          # tier2 set
            ad("b", "Umbreon holo"),                           # named card
            ad("a", "Base Set Charizard"),                     # tier1 set
        ]
        order = [r["finn_kode"] for r in fd.priority_order(records)]
        self.assertEqual(order, ["a", "b", "c", "d"],
                         f"priority wrong: {order}")

    def test_emit_priority_writes_all_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "priority.jsonl"
            records = [ad("a", "Base Set Charizard"), ad("b", "Umbreon holo")]
            p1 = fd.emit_priority(records, out)
            p2 = fd.emit_priority(records, out)
            self.assertNotEqual(p1, p2, "second write must not overwrite the first")
            lines = p1.read_text(encoding="utf-8").split("\n")
            self.assertEqual([ln for ln in lines if ln.strip()].__len__(), 2)


class TestBuild(unittest.TestCase):
    def test_writes_all_five_artifacts_and_roundtrips(self):
        with tempfile.TemporaryDirectory() as td:
            records = [ad("111", "Charizard Base Set 4/102"),
                       ad("222", "Umbreon holo")]
            pricing = {"111": pricing_rec("111", market=1500.0, ratio=15.0, delta=-1400.0)}
            summary = fd.build(records, pricing, td, ts="2026-01-02-030405")
            self.assertEqual(summary["rows"], 2)
            self.assertEqual(summary["priced"], 1)
            self.assertEqual(summary["with_ratio"], 1)

            deals_csv = Path(summary["paths"]["deals_csv"])
            self.assertTrue(deals_csv.is_file())
            with deals_csv.open(encoding="utf-8", newline="") as fh:
                rows = list(csv.reader(fh))
            self.assertEqual(rows[0], fd.COLUMNS)
            self.assertEqual(len(rows), 3, "header + 2 ads")

            sheet_csv = Path(summary["paths"]["sheet_csv"])
            with sheet_csv.open(encoding="utf-8", newline="") as fh:
                srows = list(csv.reader(fh))
            self.assertEqual(srows[0], fd.SHEET_COLUMNS)
            self.assertEqual(len(srows), 3)

            html = Path(summary["paths"]["deals_html"]).read_text(encoding="utf-8")
            self.assertIn("<table>", html)
            self.assertNotIn('src="http', html)
            print(f"build summary: { {k: summary[k] for k in ('rows','priced','with_ratio')} }")


if __name__ == "__main__":
    unittest.main(verbosity=2)
