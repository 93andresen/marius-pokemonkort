#!/usr/bin/env python3
"""Regression net for ``finn/finn_ad.py`` — offline parse of a committed real capture.

Parses ``tests/fixtures/finn_ad_475878513.html`` (a real, saved FINN ad page) with the
production parser and asserts the machine-read fields against the values verified in the
live archive record ``data/finn/annonser/475878513_.../475878513.json`` (checked 2026-10-06).

No network, stdlib only.  Run with:

    uv run tests/test_finn_ad_parse.py
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

import finn_ad  # noqa: E402  (needs the sys.path insert above)

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "finn_ad_475878513.html"


class ParseRealCapture(unittest.TestCase):
    """Assert parse_ad()'s output on a real saved page equals the verified truth."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.html = FIXTURE.read_text(encoding="utf-8")
        cls.rec = finn_ad.parse_ad(cls.html)
        # Self-evidencing: print the key observed values for the record.
        r = cls.rec
        print(
            "[fixture parse] kode={k!r} status={s!r} price={p!r} gallery={g!r} "
            "images={n!r} quality={q!r} missing={m!r} warnings={w!r}".format(
                k=r.get("finn_kode"), s=r.get("status"), p=r.get("price_nok"),
                g=r.get("gallery_count"), n=r.get("image_count_from_html"),
                q=r.get("parse_quality"), m=r.get("missing_fields"), w=r.get("warnings"),
            )
        )

    def test_identity_and_cross_check(self) -> None:
        self.assertEqual(self.rec["finn_kode"], "475878513")
        cands = self.rec["kode_candidates"]
        # canonical link, FINN-kode line, map adId, contact-button adId must all agree.
        self.assertEqual(set(cands.keys()),
                         {"canonical", "object_info", "maplink", "contact_button"})
        self.assertEqual(set(cands.values()), {"475878513"})

    def test_title_status_price(self) -> None:
        self.assertEqual(
            self.rec["title"],
            "Stort vintage salg av Pokemon Holo/Rare/Japansk (Fastpris)",
        )
        self.assertEqual(self.rec["status"], "Inaktiv")
        self.assertEqual(self.rec["trade_type"], "Til salgs")
        self.assertEqual(self.rec["price_label"], "100 kr")
        self.assertEqual(self.rec["price_nok"], 100)

    def test_location(self) -> None:
        self.assertEqual(self.rec["location_text"], "1366 Lysaker")
        self.assertEqual(self.rec["postal_code"], "1366")
        self.assertAlmostEqual(self.rec["lat"], 59.907879864471965, places=6)
        self.assertAlmostEqual(self.rec["lon"], 10.629192367849328, places=6)

    def test_last_modified(self) -> None:
        self.assertEqual(self.rec["last_modified_raw"], "8.9.2026 kl. 18:44")
        self.assertEqual(self.rec["last_modified"], "2026-09-08T18:44:00")

    def test_gallery_and_images(self) -> None:
        self.assertEqual(self.rec["gallery_count"], 25)
        self.assertEqual(self.rec["image_count_from_html"], 25)
        self.assertEqual(len(self.rec["image_uuids"]), 25)
        # No duplicate uuids, and every candidate is a well-formed uuid for this ad.
        self.assertEqual(len(set(self.rec["image_uuids"])), 25)
        for cand in self.rec["image_candidates"]:
            self.assertEqual(cand["item_ref"], "475878513")
            self.assertEqual(len(cand["uuid"]), 36)

    def test_description_has_card_list(self) -> None:
        desc = self.rec["description_raw"]
        self.assertIsNotNone(desc)
        self.assertIn("Liste over kort:", desc)
        self.assertIn("Venusaur", desc)
        self.assertNotIn("Vis hele beskrivelsen", desc)  # UI control stripped

    def test_breadcrumbs(self) -> None:
        self.assertEqual(
            self.rec["breadcrumbs"],
            ["Torget", "Fritid, hobby og underholdning", "Samleobjekter", "Samlekort"],
        )

    def test_similar_ads_present(self) -> None:
        ads = self.rec["similar_ads"]
        self.assertGreater(len(ads), 0, "expected 'Mer som dette' recommendations")
        for a in ads:
            self.assertTrue(a["item_id"])
            self.assertTrue(a["url"].startswith("https://www.finn.no/"))

    def test_quality_full_no_warnings(self) -> None:
        self.assertEqual(self.rec["parse_quality"], "full")
        self.assertEqual(self.rec["missing_fields"], [])
        self.assertEqual(self.rec["warnings"], [])


class ValueParsers(unittest.TestCase):
    """The two small value parsers must handle the shapes seen on real pages."""

    def test_parse_nok(self) -> None:
        cases = [
            ("100 kr", 100),
            ("1 200 kr", 1200),
            ("1.200,-", 1200),
            ("1\u00a0200 kr", 1200),  # non-breaking space thousands separator
            (None, None),
            ("Gis bort", None),  # no digits -> None (parse_ad maps "gis bort" to 0)
        ]
        for raw, expected in cases:
            self.assertEqual(finn_ad._parse_nok(raw), expected, f"input={raw!r}")

    def test_parse_norwegian_datetime(self) -> None:
        self.assertEqual(
            finn_ad._parse_norwegian_datetime("8.9.2026", "18:44"),
            "2026-09-08T18:44:00",
        )
        self.assertEqual(
            finn_ad._parse_norwegian_datetime("21.12.1999", "09:05"),
            "1999-12-21T09:05:00",
        )


class FailureModes(unittest.TestCase):
    """The parser must fail loudly rather than claim success on bad input."""

    def test_empty_page_is_failed(self) -> None:
        rec = finn_ad.parse_ad("<html></html>")
        self.assertEqual(rec["parse_quality"], "failed")
        self.assertIsNone(rec["finn_kode"])
        self.assertIsNone(rec["title"])
        self.assertIn("finn_kode", rec["missing_fields"])
        self.assertIn("title", rec["missing_fields"])

    def test_gallery_count_mismatch_warns(self) -> None:
        # Header claims 9 images; only 1 uuid for this item is present in the HTML.
        html = (
            '<link rel="canonical" href="https://www.finn.no/recommerce/forsale/item/123456789">'
            "<h1>Test</h1>"
            "<div>Bilde (1/9)</div>"
            '<img src="https://images.finncdn.no/dynamic/1280w/item/123456789/'
            'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee">'
        )
        rec = finn_ad.parse_ad(html)
        self.assertEqual(rec["gallery_count"], 9)
        self.assertEqual(rec["image_count_from_html"], 1)
        self.assertTrue(
            any("gallery_count" in w for w in rec["warnings"]),
            f"expected a gallery_count mismatch warning, got {rec['warnings']!r}",
        )

    def test_kode_disagreement_warns(self) -> None:
        # canonical says 111111111, the FINN-kode line says 222222222 -> loud warning.
        html = (
            '<link rel="canonical" href="https://www.finn.no/recommerce/forsale/item/111111111">'
            "FINN-kode 222222222"
            "<h1>Test</h1>"
        )
        rec = finn_ad.parse_ad(html)
        self.assertEqual(set(rec["kode_candidates"].values()), {"111111111", "222222222"})
        self.assertTrue(
            any("disagreement" in w for w in rec["warnings"]),
            f"expected a kode-disagreement warning, got {rec['warnings']!r}",
        )


class RegistryInput(unittest.TestCase):
    """The discovery registry must be scrapable directly (its keys are FINN-koder)."""

    def test_load_registry_kodes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            reg = Path(td) / "pokemon-kort.json"
            reg.write_text(
                json.dumps({
                    "478215833": {"heading": "b"},
                    "458560266": {"heading": "a"},
                    "477798898": {"heading": "c"},
                    "/recommerce/forsale/item/458560266": {"heading": "dup-kode"},
                    "not-a-kode": {"heading": "noise"},
                }),
                encoding="utf-8",
            )
            self.assertEqual(
                finn_ad.load_registry_kodes(reg),
                ["458560266", "477798898", "478215833"],
            )

    def test_load_registry_kodes_missing_file(self) -> None:
        self.assertEqual(
            finn_ad.load_registry_kodes(Path("definitely/not/here.json")), []
        )

    def test_cli_from_registry_missing_is_error(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = finn_ad.main(["--from-registry", "definitely/not/here.json"])
        self.assertEqual(rc, 2)
        self.assertIn("registry not found", buf.getvalue())  # loud, not a silent no-op


if __name__ == "__main__":
    if not FIXTURE.is_file():
        raise SystemExit(f"FIXTURE MISSING: {FIXTURE} — cannot run regression net")
    unittest.main(verbosity=2)
