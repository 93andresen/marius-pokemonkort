#!/usr/bin/env python3
"""Tests for ``finn/finn_tables.py`` — assemble pricing records into tables.

Everything here is **pure formatting**: no network, no PokeWallet, no cache.
The records fed in are hand-built to exercise the flat-row projection, the
missing-value policy, best-deal-first ordering, CSV round-tripping, and the
self-contained sortable HTML.

Run with:  uv run tests/test_finn_tables.py
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "finn"))

import finn_tables as ft  # noqa: E402


# --- fixtures -------------------------------------------------------------- #


def card(name: str, count: int = 1, *, confidence: str = "high",
         priced: bool = True, unit: float = 2.0) -> dict:
    """One enumerated-card row, shaped like ``finn_price`` produces."""
    return {
        "name": name, "count": count, "variants": [], "line_index": 1,
        "query": name, "queries": [name], "pk_id": "pk_" + name.lower(),
        "pk_name": name, "pk_set_name": "Base Set", "pk_card_number": "4",
        "score": 80, "confidence": confidence, "flags": [],
        "price_native": 2.0, "price_currency": "USD", "price_source": "tcgplayer",
        "unit_market_value_nok": unit,
        "market_value_nok": (unit * count) if priced else None,
        "priced": priced,
    }


def pricing(kode: str = "111", *, ratio: float | None = 2.0,
            asking: float | None = 100.0, market: float | None = 200.0,
            cards: list[dict] | None = None, flags: list[str] | None = None,
            confidence: str = "high") -> dict:
    """A minimal ``finn_price.price_ad`` output record."""
    cards = cards or []
    priced = sum(1 for c in cards if c.get("priced"))
    if asking is not None and market is not None:
        delta = asking - market
    else:
        delta = None
    return {
        "price_version": "finn_price/1.0.0",
        "generated_at": "2026-10-08T03:00:00Z",
        "finn_kode": kode,
        "url": None,
        "heading": f"Ad {kode}",
        "finn_price_nok": asking,
        "identify": {"intent_rank": 1, "intent": "tier1-set",
                     "matched_set_names": ["Base Set"], "matched_card_names": []},
        "set_hints": ["Base Set"],
        "listing": {},
        "listing_confidence": confidence,
        "listing_value_nok": market if not cards else None,
        "cards": cards,
        "card_coverage": {"total": len(cards), "considered": len(cards),
                          "priced": priced, "unpriced": len(cards) - priced},
        "partial_card_coverage": bool(cards) and priced < len(cards),
        "deal": {"market_value_nok": market, "asking_price_nok": asking,
                 "delta_nok": delta, "ratio": ratio,
                 "basis": "card_list_sum" if cards else ("listing_best" if market else "none")},
        "calls_spent": 0, "cache_hit": False,
        "flags": flags or [],
        "notes": [],
    }


# --- listings projection --------------------------------------------------- #


class ListingRow(unittest.TestCase):
    def test_listing_row_fields(self) -> None:
        rec = pricing("111", ratio=2.0)
        row = ft.listing_row(rec)
        self.assertEqual(set(row.keys()), set(ft.LISTING_COLUMNS))
        self.assertEqual(len(ft.LISTING_COLUMNS), 16)
        self.assertEqual(row["ratio"], rec["deal"]["ratio"])
        self.assertEqual(row["asking_price_nok"], 100.0)
        self.assertEqual(row["market_value_nok"], 200.0)
        self.assertEqual(row["intent"], "tier1-set")
        self.assertEqual(row["cards_total"], 0)
        self.assertEqual(row["flags"], "")

    def test_flags_joined(self) -> None:
        row = ft.listing_row(pricing("x", flags=["a b", "c"]))
        self.assertEqual(row["flags"], "a b; c")


# --- cards expansion ------------------------------------------------------- #


class CardsExpansion(unittest.TestCase):
    def test_cards_expansion(self) -> None:
        cards = [card("A"), card("B", count=2), card("C", priced=False)]
        rec = pricing("222", cards=cards)
        rows = ft.card_rows(rec)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r["finn_kode"] == "222" for r in rows))
        self.assertEqual([r["name"] for r in rows], ["A", "B", "C"])
        self.assertEqual(rows[1]["count"], 2)
        self.assertFalse(rows[2]["priced"])

    def test_build_card_count_matches_sum(self) -> None:
        recs = [pricing("a", cards=[card("A"), card("B")]),
                pricing("b", cards=[card("C")])]
        rows = [r for rec in recs for r in ft.card_rows(rec)]
        self.assertEqual(len(rows), sum(len(r["cards"]) for r in recs))


# --- missing values -------------------------------------------------------- #


class MissingValues(unittest.TestCase):
    def test_missing_values_blank(self) -> None:
        rec = pricing("333", ratio=None, asking=None, market=None)
        rows = [ft.listing_row(rec)]
        with tempfile.TemporaryDirectory() as td:
            p = ft.write_csv(Path(td) / "l.csv", rows, ft.LISTING_COLUMNS)
            data = list(csv.reader(p.read_text(encoding="utf-8").splitlines()))
        header, first = data[0], data[1]
        for col in ("asking_price_nok", "market_value_nok", "delta_nok", "ratio"):
            self.assertEqual(first[header.index(col)], "", f"CSV {col} should be blank")

    def test_missing_values_dash_in_html(self) -> None:
        rec = pricing("333", ratio=None, asking=None, market=None)
        html = ft.render_html([ft.listing_row(rec)], ["market_value_nok", "ratio"], title="t")
        self.assertEqual(html.count("<td>—</td>"), 2)


# --- ordering -------------------------------------------------------------- #


class Ordering(unittest.TestCase):
    def test_sort_best_deals_first(self) -> None:
        rows = [
            ft.listing_row(pricing("a", ratio=0.5)),
            ft.listing_row(pricing("b", ratio=2.0)),
            ft.listing_row(pricing("c", ratio=None, asking=None, market=None)),
        ]
        ordered = ft.sort_listings(rows)
        self.assertEqual([r["finn_kode"] for r in ordered], ["b", "a", "c"])

    def test_sort_is_deterministic_tiebreak(self) -> None:
        rows = [ft.listing_row(pricing("z", ratio=1.0)),
                ft.listing_row(pricing("a", ratio=1.0))]
        ordered = ft.sort_listings(rows)
        self.assertEqual([r["finn_kode"] for r in ordered], ["a", "z"])


# --- CSV round-trip -------------------------------------------------------- #


class CsvRoundtrip(unittest.TestCase):
    def test_csv_roundtrip(self) -> None:
        rows = [ft.listing_row(pricing("a", ratio=2.0)),
                ft.listing_row(pricing("b", ratio=0.5))]
        with tempfile.TemporaryDirectory() as td:
            p = ft.write_csv(Path(td) / "x.csv", rows, ft.LISTING_COLUMNS)
            with p.open(newline="", encoding="utf-8") as fh:
                data = list(csv.reader(fh))
        self.assertEqual(data[0], ft.LISTING_COLUMNS)
        self.assertEqual(len(data), 1 + len(rows))


# --- HTML ------------------------------------------------------------------ #


class Html(unittest.TestCase):
    def test_html_self_contained_and_sortable(self) -> None:
        rows = [ft.listing_row(pricing("a", ratio=2.0))]
        html = ft.render_html(rows, ft.LISTING_COLUMNS, title="deals")
        self.assertIn("<script>", html)
        self.assertIn("sortTable", html)
        self.assertIn("onclick", html)
        self.assertIn("<th", html)
        self.assertIn("<td", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("<script src", html)
        self.assertNotIn("<link", html)


# --- CLI ------------------------------------------------------------------- #


class Cli(unittest.TestCase):
    def test_cli_writes_timestamped_files(self) -> None:
        recs = [pricing("a", ratio=2.0), pricing("b", ratio=0.5)]
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "pricing.jsonl"
            src.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
            out = Path(td) / "tables"
            buf, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                rc = ft.main(["--from-jsonl", str(src), "--outdir", str(out),
                              "--ts", "2026-01-02-030405", "--json"])
            self.assertEqual(rc, 0)
            names = sorted(p.name for p in out.iterdir())
            self.assertEqual(names, [
                "cards_2026-01-02-030405.csv",
                "listings_2026-01-02-030405.csv",
                "listings_2026-01-02-030405.html",
            ])
            summary = json.loads(buf.getvalue())
            self.assertEqual(summary["listings"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
