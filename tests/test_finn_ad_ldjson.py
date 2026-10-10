#!/usr/bin/env python3
"""JSON-LD price fallback for ``finn/finn_ad.py``.

The FINN ad page carries a ``<script type="application/ld+json">`` Product block
whose ``offers.price`` is the seller's asking price, scoped to the ad itself. The
``Til salgs`` DOM anchor (spec §2.1) sometimes misses on newer captures; the JSON-LD
block then fills ``price_nok`` — and, being scoped to this ad, it can never pick up a
"Mer som dette" price (the trap spec §2.1 warns about). ``sku`` doubles as a free
identity cross-check against the FINN-kode.

Run:  uv run tests/test_finn_ad_ldjson.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "finn"))  # noqa: E402

import finn_ad  # noqa: E402

# A minimal page holding only the schema.org block (no ``Til salgs`` DOM label).
LD_HTML = """<!doctype html><html><head>
<script type="application/ld+json">{
  "@context": "https://schema.org",
  "@type": "Product",
  "sku": "477803639",
  "url": "https://www.finn.no/recommerce/forsale/item/477803639",
  "name": "Psychic Energy #101 Base Set (1999)",
  "offers": {"@type": "Offer", "price": "9", "priceCurrency": "NOK",
             "availability": "https://schema.org/InStock"}
}</script></head><body></body></html>"""


class LdJsonPriceFallback(unittest.TestCase):
    def test_extract_reads_price_sku_name(self) -> None:
        ld = finn_ad.extract_product_ldjson(LD_HTML)
        assert ld is not None
        self.assertEqual(ld["sku"], "477803639")
        self.assertEqual(ld["price_nok"], 9)
        self.assertEqual(ld["price_currency"], "NOK")
        self.assertEqual(ld["name"], "Psychic Energy #101 Base Set (1999)")

    def test_parse_ad_falls_back_to_ldjson_price(self) -> None:
        # No ``Til salgs`` DOM label here → price must come from JSON-LD.
        rec = finn_ad.parse_ad(LD_HTML, kode_hint="477803639")
        self.assertEqual(rec["price_nok"], 9)
        self.assertEqual(rec["price_nok_source"], "ld+json")
        self.assertNotIn("price_nok", rec["missing_fields"])
        # title + identity also recovered from the structured block
        self.assertEqual(rec["title"], "Psychic Energy #101 Base Set (1999)")
        self.assertEqual(rec["title_source"], "ld+json")
        self.assertEqual(rec["finn_kode"], "477803639")
        self.assertEqual(rec["warnings"], [])

    def test_absent_ldjson_leaves_price_missing(self) -> None:
        rec = finn_ad.parse_ad("<html><body>nothing here</body></html>", kode_hint="111111111")
        self.assertIsNone(rec["price_nok"])
        self.assertIsNone(rec.get("ld_json"))
        self.assertIsNone(rec["price_nok_source"])
        self.assertIn("price_nok", rec["missing_fields"])

    def test_non_nok_currency_is_not_coerced_to_nok(self) -> None:
        html = LD_HTML.replace('"priceCurrency": "NOK"', '"priceCurrency": "EUR"')
        ld = finn_ad.extract_product_ldjson(html)
        assert ld is not None
        self.assertIsNone(ld["price_nok"])
        self.assertEqual(ld["price_currency"], "EUR")

    def test_sku_mismatch_is_a_loud_warning(self) -> None:
        rec = finn_ad.parse_ad(LD_HTML, kode_hint="999999999")
        # hint (999999999) vs ld sku (477803639) disagree → warning, never silent.
        self.assertTrue(any("JSON-LD sku" in w for w in rec["warnings"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
