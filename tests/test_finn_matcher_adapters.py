#!/usr/bin/env python3
"""Tests for the listing adapters in ``finn/finn_matcher.py``.

There are two record shapes in this repo and they must not be confused:

* **search records** — ``data/finn/searches/*/all_ads.jsonl`` from ``finn_search``:
  keys ``heading``, ``price_amount``, ``canonical_url``, ``location``.
* **archive ad-view records** — ``data/finn/annonser/<kode>_<slug>/<kode>.json``
  (joined by ``finn_corpus``): keys ``title``, ``price_nok``, ``url``,
  ``location_text``.

``listing_from_search`` used to read *only* the search keys, so pointing
``finn_matcher.py --from-jsonl`` at an archive corpus produced ``heading=None``
for every ad — a **silent** null (0 queries, 0 matches, no error).  These tests
pin the fix: the adapter must accept either shape.

Run with:  uv run tests/test_finn_matcher_adapters.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "finn"))

import finn_matcher as fm  # noqa: E402


class ListingFromSearch(unittest.TestCase):
    """The adapter must read both the search and the archive record shapes."""

    def test_search_record_shape(self) -> None:
        rec = {
            "finn_kode": "477805681",
            "canonical_url": "https://www.finn.no/recommerce/forsale/item/477805681",
            "heading": "Psychic Energy #101 Base Set (1999)",
            "price_amount": 9,
            "location": "Oslo",
        }
        got = fm.listing_from_search(rec)
        self.assertEqual(got["finn_kode"], "477805681")
        self.assertEqual(got["heading"], "Psychic Energy #101 Base Set (1999)")
        self.assertEqual(got["finn_price_nok"], 9)
        self.assertEqual(got["url"], rec["canonical_url"])
        self.assertEqual(got["location"], "Oslo")

    def test_archive_adview_shape(self) -> None:
        rec = {
            "finn_kode": "475878513",
            "url": "https://www.finn.no/recommerce/forsale/item/475878513",
            "title": "Stort vintage salg av Pokemon Holo/Rare/Japansk (Fastpris)",
            "price_nok": 100,
            "location_text": "Bergen",
        }
        got = fm.listing_from_search(rec)
        self.assertEqual(got["finn_kode"], "475878513")
        self.assertEqual(got["heading"], rec["title"])
        self.assertEqual(got["finn_price_nok"], 100)
        self.assertEqual(got["url"], rec["url"])
        self.assertEqual(got["location"], "Bergen")

    def test_search_keys_win_when_both_present(self) -> None:
        rec = {
            "finn_kode": "1",
            "canonical_url": "https://search-url",
            "heading": "search-heading",
            "price_amount": 5,
            "location": "search-location",
            "url": "https://adview-url",
            "title": "adview-title",
            "price_nok": 99,
            "location_text": "adview-location",
        }
        got = fm.listing_from_search(rec)
        self.assertEqual(got["heading"], "search-heading")
        self.assertEqual(got["finn_price_nok"], 5)
        self.assertEqual(got["url"], "https://search-url")
        self.assertEqual(got["location"], "search-location")

    def test_empty_record_is_blank_not_crash(self) -> None:
        got = fm.listing_from_search({})
        self.assertIsNone(got["heading"])
        self.assertIsNone(got["finn_price_nok"])
        self.assertIsNone(got["url"])
        self.assertIsNone(got["location"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
