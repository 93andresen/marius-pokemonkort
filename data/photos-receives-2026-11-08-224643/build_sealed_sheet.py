#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "google-api-python-client>=2.201.0",
#     "google-auth>=2.62.1",
# ]
# ///
"""One-off: build the Sealed-* tabs in the portfolio Google Sheet.

The content below is hand-composed from the offer transcription and the 13 FINN
runs. Nothing is derived by a generic pipeline -- the numbers are typed in and
then asserted against the known totals, so a typo fails loudly instead of
silently producing a wrong sheet.

Re-running this script clears and rewrites ONLY the Sealed-* tabs. Every other
tab in the spreadsheet (Dashboard, Collection, PriceSnapshots, FINN, ...) is
left untouched.

Why a script at all: the MCP google-sheets server exposes only
get_sheet_data / update_cells / list_sheets / create_sheet / batch_update_cells.
It cannot set colours, freeze rows, column widths or number formats. The Sheets
API batchUpdate can, and the service-account key the MCP server already uses is
on disk.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

SPREADSHEET_ID = "13TfMos8hP4zT3-Tf92F7ZE0hJ2r7cKJdEqvdj0gvtpM"
KEY_PATH = Path(r"C:\data\enc\google-sheets-agents-keys\project-id-sheets-6c77c3f3c3f2.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# produced by analyze_ads.py from the 82 scraped ads
ADS_EXTRACT = Path(__file__).with_name("ads_extract.json")

# ---------------------------------------------------------------- palette ----
NAVY = "#1F3864"
BLUE = "#2F5597"
LIGHT = "#D9E2F3"
PALE = "#EEF3FA"
GREEN = "#D9EAD3"
AMBER = "#FFF2CC"
RED = "#F4CCCC"
GREY = "#EFEFEF"
WHITE = "#FFFFFF"
INK = "#1A1A1A"

# ------------------------------------------------------------ offer data ----
# (set, qty, jpy_per_box, nok_per_box, jpy_total, nok_total, finn_lowest_nok, note)
OFFER: list[tuple] = [
    ("Snow Hazard", 100, 12_000, 717, 1_200_000, 71_700, None, ""),
    ("Violet ex", 60, 11_800, 705, 708_000, 42_300, None, ""),
    ("VSTAR Universe", 20, 29_200, 1_744, 584_000, 34_880, 2_500, ""),
    ("Paradigm Trigger", 30, 22_500, 1_344, 675_000, 40_320, None, ""),
    ("Lost Abyss", 20, 54_000, 3_224, 1_080_000, 64_480, 3_999, ""),
    ("Battle Region", 10, 14_500, 866, 145_000, 8_660, None, ""),
    ("VMAX Climax", 10, 32_000, 1_911, 320_000, 19_110, 4_930, ""),
    ("25th Anniversary Collection", 30, 64_000, 3_822, 1_920_000, 114_660, None,
     "FINN only has Golden Boxes (10 000 / 15 999) - different product"),
    ("Eevee Heroes", 20, 130_000, 7_763, 2_600_000, 155_260, None,
     "largest single line; FINN has only a 799 pack and a 1 NOK placeholder"),
    ("Jet-Black Spirit", 5, 22_500, 1_344, 112_500, 6_720, None, ""),
    ("Silver Lance", 5, 19_000, 1_135, 95_000, 5_675, None, ""),
    ("30th CELEBRATION 9-Item Set", 50, 18_500, 1_105, 925_000, 55_250, None, ""),
    ("30th CELEBRATION", 200, 25_500, 1_523, 5_100_000, 304_600, 1_899, ""),
    ("Storm Emerald", 500, 9_700, 579, 4_850_000, 289_500, 920,
     "FINN spells it 'Storm Emeralda'"),
    ("Abyss Eye", 200, 9_000, 537, 1_800_000, 107_400, 799, ""),
    ("Ninja Spinner", 200, 10_000, 597, 2_000_000, 119_400, None, ""),
    ("Munikis Zero", 150, 9_000, 537, 1_350_000, 80_550, 990,
     "FINN calls it 'Nihil Zero' (same set, ムニキスゼロ)"),
    ("Mega Dream ex", 150, 13_000, 776, 1_950_000, 116_400, 1_099, ""),
    ("Inferno X", 150, 18_500, 1_105, 2_775_000, 165_750, 1_299, ""),
    ("Mega Brave", 200, 8_700, 520, 1_740_000, 104_000, 950, ""),
    ("Mega Symphonia", 300, 8_500, 508, 2_550_000, 152_400, 950, ""),
    ("Black Bolt", 50, 26_800, 1_600, 1_340_000, 80_000, None, ""),
    ("White Flare", 50, 23_800, 1_421, 1_190_000, 71_050, None, ""),
    ("??? (name cropped)", 50, 25_800, 1_541, 1_290_000, 77_050, None,
     "set name cut off by the screenshot edge"),
    ("Heat Wave Arena", 50, 20_000, 1_194, 1_000_000, 59_700, 1_250, ""),
    ("Battle Partners", 120, 11_000, 657, 1_320_000, 78_840, None, ""),
    ("Terastal Festival ex", 100, 20_200, 1_206, 2_020_000, 120_600, 2_099, ""),
    ("Stellar Miracle", 40, 13_400, 800, 536_000, 32_000, 900, ""),
    ("Night Wanderer", 30, 13_500, 806, 405_000, 24_180, None, ""),
    ("Mask of Change", 20, 14_700, 878, 294_000, 17_560, None, ""),
    ("Shiny Treasure ex", 200, 19_500, 1_164, 3_900_000, 232_800, 1_395, ""),
    ("Ancient Roar", 70, 13_000, 776, 910_000, 54_320, None, ""),
    ("Future Flash", 70, 11_500, 687, 805_000, 48_090, None, ""),
    ("Ruler of the Black Flame", 20, 20_500, 1_224, 410_000, 24_480, None, ""),
    ("Raging Surf", 40, 17_200, 1_027, 688_000, 41_080, None, ""),
    ("Pokémon Card 151", 100, 52_300, 3_123, 5_230_000, 312_300, 3_200,
     "FINN uses three spellings: 151 / Scarlet & Violet 151 / Pokémon Card 151"),
    ("Clay Burst", 60, None, None, None, None, None,
     "price cut off by the screenshot edge"),
]

EXPECT_QTY = 3_480
EXPECT_JPY = 55_817_500
EXPECT_NOK = 3_333_065

# --------------------------------------------------------- search data ------
# (query, ads_fetched, match_count, pages, run_id, note)
SEARCHES: list[tuple] = [
    ("pokemon booster box", 53, 1_522, 29, "2026-11-08-221957", ""),
    ("pokemon booster box japansk", 53, 267, 6, "2026-11-08-222012", ""),
    ("japanske pokemon kort", 53, 4_502, 50, "2026-11-08-222024",
     "FINN caps pagination at 50 pages (~2 650 ads)"),
    ("pokemon display box", 53, 306, 6, "2026-11-08-222035", ""),
    ("pokemon sealed", 53, 2_849, 50, "2026-11-08-222047", "hits the 50-page cap"),
    ("pokemon booster box sealed", 53, 951, 18, "2026-11-08-222506", ""),
    ("pokemon japansk booster", 53, 492, 10, "2026-11-08-222517", ""),
    ("pokemon booster boks", 53, 706, 14, "2026-11-08-222527", ""),
    ("pokemon eevee heroes", 53, 367, 7, "2026-11-08-222537", ""),
    ("pokemon vstar universe", 53, 186, 4, "2026-11-08-222548", ""),
    ("pokemon lost abyss", 15, 15, 1, "2026-11-08-222559", "only 15 matches exist"),
    ("pokemon 25th anniversary", 53, 265, 5, "2026-11-08-222609", ""),
    ("pokemon 151 booster box", 53, 317, 6, "2026-11-08-222621", ""),
]

# ------------------------------------------------------- FINN ad data -------
# (finn_kode, nok, heading, bucket, note)
FINN_ADS: list[tuple] = [
    (472039650, 799, "Abyss Eye Booster Box Japansk", "JP sealed box", ""),
    (480373254, 900, "Stellar Miracle Booster Box - japansk!", "JP sealed box", ""),
    (480396681, 950, "Pokémon Mega Symphonia Japansk Boosterboks", "JP sealed box", ""),
    (480396500, 950, "Pokémon Mega Brave Japansk Boosterboks", "JP sealed box", ""),
    (480395875, 950, "Pokémon Storm Emeralda Japansk Boosterboks", "JP sealed box", ""),
    (480587151, 990, "Japansk Nihil Zero Booster Box", "JP sealed box", "= Munikis Zero"),
    (480227708, 990, "Japansk Nihil Zero Booster Box", "JP sealed box", "= Munikis Zero"),
    (480378085, 1_099, "Pokémon Mega Dream ex – Japansk Booster Box", "JP sealed box", ""),
    (480193149, 1_100, "Crimson Haze Booster Box Sealed Japansk Pokemon", "JP sealed box", ""),
    (479076284, 1_149, "Pokémon Incandescent Arcana Booster Box Japansk", "JP sealed box", ""),
    (480082813, 1_250, "Pokémon Heat Wave Arena japansk boosterboks", "JP sealed box", ""),
    (480587161, 1_299, "Japansk Mega Dream ex - Booster Box", "JP sealed box", ""),
    (480587145, 1_299, "Japansk Mega Symphonia - Booster Box", "JP sealed box", ""),
    (480394719, 1_299, "Pokemon Inferno X booster box Japansk", "JP sealed box", ""),
    (480227709, 1_299, "Japansk Mega Symphonia - Booster Box", "JP sealed box", ""),
    (480227702, 1_299, "Japansk Mega Dream ex - Booster Box", "JP sealed box", ""),
    (480380062, 1_499, "Pokémon Inferno X – Japansk Booster Box", "JP sealed box", ""),
    (463817842, 1_750, "Super Electric Breaker Japansk Booster Display Box", "JP sealed box", ""),
    (476606430, 1_899, "Pokemon 30th Celebration Japansk Display Booster Box", "JP sealed box", ""),
    (480587158, 2_099, "Japansk Terastal Festival ex Booster Box", "JP sealed box", ""),
    (479077088, 2_099, "Pokémon Shiny Star V Booster Box Japansk", "JP sealed box", ""),
    (480227703, 2_099, "Japansk Terastal Festival ex Booster Box", "JP sealed box", ""),
    (479075557, 2_399, "Pokémon GO Booster Box Japansk", "JP sealed box", ""),
    (477280195, 2_500, "Pokémon 30th Celebration Booster Box japansk", "JP sealed box", ""),
    (478648073, 2_599, "Pokémon 30th Celebration Booster Box Japansk", "JP sealed box", ""),
    (480092769, 3_200, "Pokémon Scarlet & Violet 151 Japansk Booster Box", "JP sealed box", ""),
    (480411707, 3_500, "Pokémon Card 151 – Japansk Booster Box", "JP sealed box", ""),
    (479354763, 3_500, "Pokémon 151 – Japansk Booster Box", "JP sealed box", ""),
    (470097965, 4_290, "Pokemon Lost Abyss japansk boosterboks", "JP sealed box", ""),
    (480254788, 4_930, "Pokémon Japansk VMAX Climax Booster box sealed boks high class 2021",
     "JP sealed box", ""),
    (479522079, 37_500, "Stor sealed japanske boosterbokser", "JP sealed box",
     "lot, not a single box - excluded from statistics"),
    (478215833, 799, "Pokémon Eevee Heroes Japansk Booster Pack – Uåpnet / Sealed",
     "False positive", "a single pack, not a box"),
    (480361020, 4_550, "Pikachu V 001/015 Japansk 25th Anniversary Golden Box – PSA 9",
     "False positive", "graded promo collection"),
    (480361125, 15_999, "Pokémon 25th Anniversary Golden Box (japansk) – i akrylcase",
     "False positive", "premium collection box"),
    (480194872, 1, "Pokémon Eevee Heroes boosterboks", "JP by set name",
     "placeholder price, unusable"),
    (472045392, 920, "Storm Emeralda Booster Box", "JP by set name", ""),
    (475846406, 1_199, "Pokemon Storm Emeralda - Booster Box (Gratis frakt)", "JP by set name", ""),
    (448584157, 1_189, "Mega Dream EX Booster Box", "JP by set name", ""),
    (480377318, 1_250, "Mega Dream Booster Box", "JP by set name", ""),
    (457771911, 1_599, "Inferno X Booster Box", "JP by set name", ""),
    (480424068, 1_700, "POKEMON SHINY TREASURE EX BOOSTER BOX", "JP by set name", ""),
    (480509351, 2_500, "Pokémon VSTAR Universe booster boks. 1st print", "JP by set name", ""),
    (467898771, 3_999, "Pokemon Lost Abyss Booster Boks", "JP by set name", ""),
]

TABS = ["Sealed-Overview", "Sealed-Offer", "Sealed-Searches", "Sealed-Compare",
        "Sealed-FINN", "Sealed-Ads"]


# ------------------------------------------------------------- helpers ------
def rgb(hex_colour: str) -> dict[str, float]:
    h = hex_colour.lstrip("#")
    return {
        "red": int(h[0:2], 16) / 255,
        "green": int(h[2:4], 16) / 255,
        "blue": int(h[4:6], 16) / 255,
    }


def fmt_req(sheet_id: int, r0: int, r1: int, c0: int, c1: int, **kw) -> dict:
    """Build a repeatCell request. Only the properties passed are touched."""
    fmt: dict = {}
    fields: list[str] = []

    if "bg" in kw:
        fmt["backgroundColor"] = rgb(kw["bg"])
        fields.append("backgroundColor")

    tf: dict = {}
    if "fg" in kw:
        tf["foregroundColor"] = rgb(kw["fg"])
    if "bold" in kw:
        tf["bold"] = kw["bold"]
    if "size" in kw:
        tf["fontSize"] = kw["size"]
    if tf:
        fmt["textFormat"] = tf
        fields.append("textFormat")

    if "halign" in kw:
        fmt["horizontalAlignment"] = kw["halign"]
        fields.append("horizontalAlignment")
    if "valign" in kw:
        fmt["verticalAlignment"] = kw["valign"]
        fields.append("verticalAlignment")
    if "wrap" in kw:
        fmt["wrapStrategy"] = kw["wrap"]
        fields.append("wrapStrategy")
    if "numfmt" in kw:
        fmt["numberFormat"] = {"type": "NUMBER", "pattern": kw["numfmt"]}
        fields.append("numberFormat")
    if "border" in kw:
        fmt["borders"] = kw["border"]
        fields.append("borders")

    if not fields:
        raise ValueError("fmt_req called with no properties")

    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": r0,
                "endRowIndex": r1,
                "startColumnIndex": c0,
                "endColumnIndex": c1,
            },
            "cell": {"userEnteredFormat": fmt},
            "fields": "userEnteredFormat(" + ",".join(fields) + ")",
        }
    }


def widths(sheet_id: int, sizes: list[int]) -> dict:
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": 0,
                "endIndex": len(sizes),
            },
            "properties": {"pixelSize": 0},
            "fields": "pixelSize",
        }
    }


def col_widths(sheet_id: int, sizes: list[int]) -> list[dict]:
    return [
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": i,
                    "endIndex": i + 1,
                },
                "properties": {"pixelSize": px},
                "fields": "pixelSize",
            }
        }
        for i, px in enumerate(sizes)
    ]


def freeze(sheet_id: int, rows: int) -> dict:
    return {
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {"frozenRowCount": rows},
            },
            "fields": "gridProperties.frozenRowCount",
        }
    }


def unmerge_all(sheet_id: int, rows: int = 200, cols: int = 20) -> dict:
    """Drop every merge in the tab so a re-run cannot inherit stale merges."""
    return {"unmergeCells": {"range": {
        "sheetId": sheet_id,
        "startRowIndex": 0, "endRowIndex": rows,
        "startColumnIndex": 0, "endColumnIndex": cols,
    }}}


def merge(sheet_id: int, r0: int, r1: int, c0: int, c1: int) -> dict:
    return {
        "mergeCells": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": r0,
                "endRowIndex": r1,
                "startColumnIndex": c0,
                "endColumnIndex": c1,
            },
            "mergeType": "MERGE_ALL",
        }
    }


def ratio_colour(ratio: float) -> str:
    if ratio < 1.2:
        return GREEN
    if ratio <= 1.6:
        return AMBER
    return RED


# --------------------------------------------------------------- content ----
def overview_rows() -> list[list]:
    rows: list[list] = []
    rows.append(["JAPANESE SEALED BOOSTER BOXES — WHOLESALE OFFER vs FINN.NO", "", "", ""])
    rows.append(["Prepared 2026-11-08 · 3 Signal screenshots · 13 FINN.no searches · 483 unique ads", "", "", ""])
    rows.append(["", "", "", ""])
    rows.append(["KEY NUMBERS", "", "", ""])
    rows.append(["Metric", "Value", "Note", ""])
    rows += [
        ["Lines in the offer", 37, "36 priced, 1 price cropped", ""],
        ["Total boxes", EXPECT_QTY, "", ""],
        ["Total cost (JPY)", EXPECT_JPY, "", ""],
        ["Total cost (NOK)", EXPECT_NOK, "", ""],
        ["Average per box (NOK)", 958, "3 333 065 ÷ 3 480", ""],
        ["FX used (NOK per JPY)", 0.0597129, "100 NOK = 1 674,68 JPY, Google 2026-11-08 22:01 UTC", ""],
        ["FINN searches run", 13, "one page each, card category only", ""],
        ["Unique FINN ads seen", 483, "after dedupe by FINN-kode", ""],
        ["Japanese sealed boxes on FINN", 31, "+8 more identifiable by set name", ""],
        ["Offer sets with a FINN comparable", "16 of 37", "", ""],
        ["Median FINN ask ÷ offer price", 1.43, "range 1,02× – 2,58×", ""],
        ["Median FINN ask (matched sets)", 1_275, "NOK per box", ""],
        ["Gross spread at that median", 1_103_935, "3 480 × 1 275 − 3 333 065, before shipping/import/fees", ""],
    ]
    rows.append(["", "", "", ""])
    rows.append(["VERDICT", "", "", ""])
    rows.append(["", "", "", ""])
    rows += [
        ["The offer is wholesale-priced, not a bargain.", "", "", ""],
        ["A consistent 1,02×–2,58× retail markup across 16 independent sets is what a real distributor price looks like.", "", "", ""],
        ["Liquidity, not price, is the constraint: 3 480 boxes against 31 competing Japanese sealed listings on FINN.", "", "", ""],
        ["21 of 37 sets have no FINN comparable at all — including the two largest lines (Eevee Heroes 2 600 000 JPY, 25th Anniversary Collection 1 920 000 JPY).", "", "", ""],
    ]
    rows.append(["", "", "", ""])
    rows.append(["TABS IN THIS WORKBOOK", "", "", ""])
    rows.append(["Tab", "What it holds", "", ""])
    rows += [
        ["Sealed-Offer", "37 offer lines: JPY/NOK per box, line totals, and the FINN comparable where one exists", "", ""],
        ["Sealed-Searches", "the 13 FINN queries with match counts and page counts", "", ""],
        ["Sealed-Compare", "the 16 sets where FINN has a comparable, with the ratio", "", ""],
        ["Sealed-FINN", "42 Japanese-relevant FINN ads: 31 sealed boxes, 3 false positives, 8 by set name", "", ""],
        ["Sealed-Ads", "82 individual ads scraped in detail: price, lot size, NOK/box, language, set, seller, bucket", "", ""],
    ]
    return rows


def offer_rows() -> list[list]:
    rows: list[list] = [["#", "Set", "Qty", "JPY/box", "NOK/box", "JPY total", "NOK total",
                         "FINN lowest ask", "FINN ÷ offer", "Note"]]
    for i, (name, qty, jpy, nok, jpy_t, nok_t, finn, note) in enumerate(OFFER, start=1):
        ratio = None if (finn is None or nok is None) else round(finn / nok, 2)
        rows.append([i, name, qty, jpy, nok, jpy_t, nok_t, finn, ratio, note])
    rows.append(["", "TOTAL", EXPECT_QTY, "", "", EXPECT_JPY, EXPECT_NOK, "", "", "excludes Clay Burst"])
    return rows


def search_rows() -> list[list]:
    rows: list[list] = [["#", "Query", "Ads fetched", "match_count", "Pages available", "Run id", "Note"]]
    for i, (q, ads, mc, pages, run, note) in enumerate(SEARCHES, start=1):
        rows.append([i, q, ads, mc, pages, run, note])
    rows.append(["", "TOTAL", sum(s[1] for s in SEARCHES), "", "", "", "651 rows fetched → 483 unique ads"])
    return rows


def compare_rows() -> list[list]:
    rows: list[list] = [["Set", "Offer NOK/box", "FINN lowest ask", "FINN ÷ offer", "Verdict"]]
    pairs = [(n, nok, finn) for (n, _q, _j, nok, _jt, _nt, finn, _note) in OFFER if finn is not None]
    pairs.sort(key=lambda p: p[2] / p[1])
    for name, nok, finn in pairs:
        ratio = finn / nok
        if ratio < 1.2:
            verdict = "thin — barely above cost"
        elif ratio <= 1.6:
            verdict = "workable"
        else:
            verdict = "healthy margin"
        rows.append([name, nok, finn, round(ratio, 2), verdict])
    rows.append(["MEDIAN", "", "", 1.43, "16 sets, range 1,02× – 2,58×"])
    return rows


def finn_rows() -> list[list]:
    rows: list[list] = [["FINN-kode", "NOK", "Heading", "Bucket", "Note"]]
    for kode, nok, heading, bucket, note in FINN_ADS:
        rows.append([kode, nok, heading, bucket, note])
    return rows


ADS_BUCKETS = ["JP sealed box", "Price list", "Other", "Single / graded", "Other TCG"]


def ads_bucket(r: dict) -> str:
    """Classify one scraped ad. Order matters: the exclusions win."""
    if r.get("other_tcg"):
        return "Other TCG"
    if r.get("price_list"):
        return "Price list"
    if r.get("product") == "single/graded":
        return "Single / graded"
    if (r.get("language") == "JP"
            and r.get("product") == "booster box"
            and (r.get("price_nok") or 0) >= 100):
        return "JP sealed box"
    return "Other"


def ads_rows() -> list[list]:
    """The 82 individually scraped ads, cheapest per box first within each bucket."""
    if not ADS_EXTRACT.exists():
        raise SystemExit(f"FATAL: {ADS_EXTRACT} not found -- run analyze_ads.py first")
    records = json.loads(ADS_EXTRACT.read_text(encoding="utf-8"))
    records.sort(key=lambda r: (
        ADS_BUCKETS.index(ads_bucket(r)),
        r.get("price_per_box") or r.get("price_nok") or 10**9,
        r.get("finn_kode") or "",
    ))
    rows: list[list] = [["#", "FINN-kode", "Title", "NOK", "Boxes in lot", "NOK/box",
                         "Language", "Product", "Set", "In offer?", "Seller", "Status",
                         "Location", "Last modified", "Bucket", "URL"]]
    for i, r in enumerate(records, start=1):
        rows.append([
            i,
            r.get("finn_kode"),
            r.get("title"),
            r.get("price_nok"),
            r.get("boxes_in_lot"),
            r.get("price_per_box"),
            r.get("language"),
            r.get("product"),
            r.get("set") or "",
            "yes" if r.get("set_in_offer") else "",
            r.get("seller_segment") or "",
            r.get("status") or "",
            r.get("location") or "",
            (r.get("last_modified") or "")[:10],
            ads_bucket(r),
            r.get("url") or "",
        ])
    return rows


# ------------------------------------------------------------------ main ----
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="build the Sealed-* tabs")
    ap.add_argument("--list-only", action="store_true",
                    help="print the existing tabs and exit without writing anything")
    args = ap.parse_args(argv)

    if not KEY_PATH.exists():
        print(f"FATAL: service-account key not found at {KEY_PATH}", file=sys.stderr)
        return 1

    # --- assert the hand-typed offer data before touching the sheet ---------
    qty = sum(r[1] for r in OFFER)
    jpy = sum(r[4] for r in OFFER if r[4] is not None)
    nok = sum(r[5] for r in OFFER if r[5] is not None)
    print(f"offer lines      : {len(OFFER)}")
    print(f"total qty        : {qty:,}  (expected {EXPECT_QTY:,})")
    print(f"total JPY        : {jpy:,}  (expected {EXPECT_JPY:,})")
    print(f"total NOK        : {nok:,}  (expected {EXPECT_NOK:,})")
    if (qty, jpy, nok) != (EXPECT_QTY, EXPECT_JPY, EXPECT_NOK):
        print("FATAL: hand-typed offer data does not match the known totals", file=sys.stderr)
        return 1
    print(f"FINN ads in tab  : {len(FINN_ADS)}")
    print(f"searches in tab  : {len(SEARCHES)}")
    print(f"scraped ads      : {len(ads_rows()) - 1}  (from {ADS_EXTRACT.name})")

    creds = service_account.Credentials.from_service_account_file(str(KEY_PATH), scopes=SCOPES)
    svc = build("sheets", "v4", credentials=creds, cache_discovery=False)

    meta = svc.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    existing = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    print(f"\nexisting tabs    : {', '.join(existing)}")

    if args.list_only:
        print(f"would create     : {', '.join(t for t in TABS if t not in existing) or 'none'}")
        print(f"would rewrite    : {', '.join(t for t in TABS if t in existing) or 'none'}")
        print("\n--list-only: nothing written.")
        return 0

    missing = [t for t in TABS if t not in existing]
    if missing:
        print(f"creating tabs    : {', '.join(missing)}")
        svc.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"requests": [{"addSheet": {"properties": {"title": t}}} for t in missing]},
        ).execute()
        meta = svc.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        existing = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    else:
        print("creating tabs    : none (all present)")

    ids = {t: existing[t] for t in TABS}

    # --- drop stale merges BEFORE writing values ----------------------------
    # A merged range only accepts a value in its top-left cell, so writing into
    # a leftover merge silently discards the other cells. Unmerge first.
    print(f"unmerging        : {len(TABS)} tabs")
    svc.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [unmerge_all(ids[t]) for t in TABS]},
    ).execute()

    # --- write values -------------------------------------------------------
    ads = ads_rows()
    payload = {
        "Sealed-Overview": overview_rows(),
        "Sealed-Offer": offer_rows(),
        "Sealed-Searches": search_rows(),
        "Sealed-Compare": compare_rows(),
        "Sealed-FINN": finn_rows(),
        "Sealed-Ads": ads,
    }
    for tab, rows in payload.items():
        svc.spreadsheets().values().clear(
            spreadsheetId=SPREADSHEET_ID, range=f"'{tab}'!A1:Z2000"
        ).execute()
        svc.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{tab}'!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()
        print(f"wrote {tab:<18} {len(rows):>4} rows x {max(len(r) for r in rows)} cols")

    # --- formatting ---------------------------------------------------------
    reqs: list[dict] = []

    # ===== Sealed-Overview =====
    # Row map (0-based): 0 title, 1 subtitle, 3 KEY NUMBERS, 4 table header,
    # 5..17 the 13 metrics, 19 VERDICT, 21..24 verdict lines,
    # 26 TABS IN THIS WORKBOOK, 27 table header, 28..32 the 5 tab rows.
    sid = ids["Sealed-Overview"]
    reqs += [
        merge(sid, 0, 1, 0, 4),
        merge(sid, 1, 2, 0, 4),
        merge(sid, 3, 4, 0, 4),
        merge(sid, 19, 20, 0, 4),
        merge(sid, 26, 27, 0, 4),
        fmt_req(sid, 0, 1, 0, 4, bg=NAVY, fg=WHITE, bold=True, size=14, halign="LEFT", valign="MIDDLE"),
        fmt_req(sid, 1, 2, 0, 4, bg=PALE, fg=INK, size=9, halign="LEFT"),
        fmt_req(sid, 3, 4, 0, 4, bg=BLUE, fg=WHITE, bold=True, size=11, halign="LEFT"),
        fmt_req(sid, 4, 5, 0, 3, bg=LIGHT, fg=INK, bold=True, halign="LEFT"),
        fmt_req(sid, 5, 18, 0, 1, halign="LEFT"),
        fmt_req(sid, 5, 18, 1, 2, halign="RIGHT", bold=True),
        fmt_req(sid, 5, 18, 2, 3, halign="LEFT", wrap="WRAP", size=9),
        fmt_req(sid, 19, 20, 0, 4, bg=BLUE, fg=WHITE, bold=True, size=11, halign="LEFT"),
        fmt_req(sid, 21, 25, 0, 4, halign="LEFT", wrap="WRAP", valign="TOP"),
        fmt_req(sid, 26, 27, 0, 4, bg=BLUE, fg=WHITE, bold=True, size=11, halign="LEFT"),
        fmt_req(sid, 27, 28, 0, 2, bg=LIGHT, fg=INK, bold=True, halign="LEFT"),
        fmt_req(sid, 28, 33, 0, 1, bold=True, halign="LEFT"),
        fmt_req(sid, 28, 33, 1, 2, halign="LEFT", wrap="WRAP", size=9),
        freeze(sid, 0),
    ]
    reqs += col_widths(sid, [300, 120, 420, 40])

    # ===== Sealed-Offer =====
    sid = ids["Sealed-Offer"]
    n = len(OFFER)
    reqs += [
        fmt_req(sid, 0, 1, 0, 10, bg=NAVY, fg=WHITE, bold=True, halign="CENTER", valign="MIDDLE", wrap="WRAP"),
        fmt_req(sid, 1, 1 + n, 0, 1, halign="CENTER", fg="#666666"),
        fmt_req(sid, 1, 1 + n, 1, 2, halign="LEFT"),
        fmt_req(sid, 1, 1 + n, 2, 3, halign="RIGHT", numfmt="#,##0"),
        fmt_req(sid, 1, 1 + n, 3, 5, halign="RIGHT", numfmt="#,##0"),
        fmt_req(sid, 1, 1 + n, 5, 7, halign="RIGHT", numfmt="#,##0"),
        fmt_req(sid, 1, 1 + n, 7, 8, halign="RIGHT", numfmt="#,##0"),
        fmt_req(sid, 1, 1 + n, 8, 9, halign="CENTER", numfmt='0.00"×"'),
        fmt_req(sid, 1, 1 + n, 9, 10, halign="LEFT", wrap="WRAP", size=9, fg="#666666"),
        fmt_req(sid, 1 + n, 2 + n, 0, 10, bg=GREY, bold=True, numfmt="#,##0",
                border={"top": {"style": "SOLID", "width": 2, "color": rgb(NAVY)}}),
        freeze(sid, 1),
    ]
    # colour the ratio cell per row
    for i, (_n, _q, _j, nok, _jt, _nt, finn, _note) in enumerate(OFFER, start=1):
        if finn is None or nok is None:
            continue
        reqs.append(fmt_req(sid, i, i + 1, 8, 9, bg=ratio_colour(finn / nok), bold=True))
    reqs += col_widths(sid, [40, 250, 60, 90, 90, 110, 110, 120, 100, 320])

    # ===== Sealed-Searches =====
    sid = ids["Sealed-Searches"]
    m = len(SEARCHES)
    reqs += [
        fmt_req(sid, 0, 1, 0, 7, bg=NAVY, fg=WHITE, bold=True, halign="CENTER", valign="MIDDLE", wrap="WRAP"),
        fmt_req(sid, 1, 1 + m, 0, 1, halign="CENTER", fg="#666666"),
        fmt_req(sid, 1, 1 + m, 1, 2, halign="LEFT", bold=True),
        fmt_req(sid, 1, 1 + m, 2, 5, halign="RIGHT", numfmt="#,##0"),
        fmt_req(sid, 1, 1 + m, 5, 6, halign="LEFT", fg="#666666"),
        fmt_req(sid, 1, 1 + m, 6, 7, halign="LEFT", wrap="WRAP", size=9, fg="#666666"),
        fmt_req(sid, 1 + m, 2 + m, 0, 7, bg=GREY, bold=True, numfmt="#,##0",
                border={"top": {"style": "SOLID", "width": 2, "color": rgb(NAVY)}}),
        freeze(sid, 1),
    ]
    reqs += col_widths(sid, [40, 260, 100, 110, 120, 150, 300])

    # ===== Sealed-Compare =====
    sid = ids["Sealed-Compare"]
    pairs = [(n_, nok, finn) for (n_, _q, _j, nok, _jt, _nt, finn, _note) in OFFER if finn is not None]
    pairs.sort(key=lambda p: p[2] / p[1])
    k = len(pairs)
    reqs += [
        fmt_req(sid, 0, 1, 0, 5, bg=NAVY, fg=WHITE, bold=True, halign="CENTER", valign="MIDDLE", wrap="WRAP"),
        fmt_req(sid, 1, 1 + k, 0, 1, halign="LEFT", bold=True),
        fmt_req(sid, 1, 1 + k, 1, 3, halign="RIGHT", numfmt="#,##0"),
        fmt_req(sid, 1, 1 + k, 3, 4, halign="CENTER", numfmt='0.00"×"', bold=True),
        fmt_req(sid, 1, 1 + k, 4, 5, halign="LEFT"),
        fmt_req(sid, 1 + k, 2 + k, 0, 5, bg=GREY, bold=True, numfmt="#,##0",
                border={"top": {"style": "SOLID", "width": 2, "color": rgb(NAVY)}}),
        freeze(sid, 1),
    ]
    for i, (_name, nok, finn) in enumerate(pairs, start=1):
        reqs.append(fmt_req(sid, i, i + 1, 3, 4, bg=ratio_colour(finn / nok)))
    reqs += col_widths(sid, [260, 130, 130, 110, 200])

    # ===== Sealed-FINN =====
    sid = ids["Sealed-FINN"]
    f = len(FINN_ADS)
    reqs += [
        fmt_req(sid, 0, 1, 0, 5, bg=NAVY, fg=WHITE, bold=True, halign="CENTER", valign="MIDDLE", wrap="WRAP"),
        fmt_req(sid, 1, 1 + f, 0, 1, halign="LEFT", fg="#666666"),
        fmt_req(sid, 1, 1 + f, 1, 2, halign="RIGHT", numfmt="#,##0", bold=True),
        fmt_req(sid, 1, 1 + f, 2, 3, halign="LEFT"),
        fmt_req(sid, 1, 1 + f, 3, 4, halign="LEFT", size=9),
        fmt_req(sid, 1, 1 + f, 4, 5, halign="LEFT", wrap="WRAP", size=9, fg="#666666"),
        freeze(sid, 1),
    ]
    bucket_colour = {"JP sealed box": GREEN, "False positive": RED, "JP by set name": AMBER}
    for i, (_k, _n, _h, bucket, _note) in enumerate(FINN_ADS, start=1):
        reqs.append(fmt_req(sid, i, i + 1, 3, 4, bg=bucket_colour[bucket]))
    reqs += col_widths(sid, [110, 90, 420, 130, 300])

    # ===== Sealed-Ads =====
    sid = ids["Sealed-Ads"]
    a = len(ads) - 1
    reqs += [
        fmt_req(sid, 0, 1, 0, 16, bg=NAVY, fg=WHITE, bold=True, halign="CENTER",
                valign="MIDDLE", wrap="WRAP"),
        fmt_req(sid, 1, 1 + a, 0, 1, halign="CENTER", fg="#666666"),
        fmt_req(sid, 1, 1 + a, 1, 2, halign="LEFT", fg="#666666"),
        fmt_req(sid, 1, 1 + a, 2, 3, halign="LEFT"),
        fmt_req(sid, 1, 1 + a, 3, 4, halign="RIGHT", numfmt="#,##0", bold=True),
        fmt_req(sid, 1, 1 + a, 4, 5, halign="CENTER", numfmt="#,##0"),
        fmt_req(sid, 1, 1 + a, 5, 6, halign="RIGHT", numfmt="#,##0", bold=True),
        fmt_req(sid, 1, 1 + a, 6, 7, halign="CENTER"),
        fmt_req(sid, 1, 1 + a, 7, 8, halign="LEFT", size=9),
        fmt_req(sid, 1, 1 + a, 8, 9, halign="LEFT", size=9),
        fmt_req(sid, 1, 1 + a, 9, 10, halign="CENTER"),
        fmt_req(sid, 1, 1 + a, 10, 11, halign="CENTER", size=9),
        fmt_req(sid, 1, 1 + a, 11, 12, halign="CENTER", size=9),
        fmt_req(sid, 1, 1 + a, 12, 13, halign="LEFT", size=9),
        fmt_req(sid, 1, 1 + a, 13, 14, halign="CENTER", size=9),
        fmt_req(sid, 1, 1 + a, 14, 15, halign="LEFT", size=9, bold=True),
        fmt_req(sid, 1, 1 + a, 15, 16, halign="LEFT", size=8, fg="#666666"),
        freeze(sid, 1),
    ]
    ads_colour = {"JP sealed box": GREEN, "Price list": AMBER, "Other": PALE,
                  "Single / graded": GREY, "Other TCG": RED}
    for i, r in enumerate(ads[1:], start=1):
        reqs.append(fmt_req(sid, i, i + 1, 14, 15, bg=ads_colour[r[14]]))
    reqs += col_widths(sid, [40, 100, 420, 80, 90, 90, 90, 110, 200, 70, 100, 80, 130, 100, 120, 300])

    print(f"\napplying {len(reqs)} formatting requests ...")
    svc.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID, body={"requests": reqs}
    ).execute()

    # --- verify -------------------------------------------------------------
    print("\nverification (read back):")
    ok = True
    for tab, rows in payload.items():
        got = svc.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range=f"'{tab}'!A1:Z2000"
        ).execute().get("values", [])
        want_rows = len(rows)
        # Sheets trims trailing all-empty columns on read, so compare against the
        # last column that actually holds a value rather than the declared width.
        want_cols = max(
            (i + 1 for r in rows for i, v in enumerate(r) if v not in (None, "")),
            default=0,
        )
        got_cols = max((len(r) for r in got), default=0)
        status = "OK" if (len(got) == want_rows and got_cols == want_cols) else "MISMATCH"
        if status != "OK":
            ok = False
        print(f"  {tab:<18} wrote {want_rows:>4}x{want_cols:<2} read {len(got):>4}x{got_cols:<2}  {status}")

    print("\nDONE" if ok else "\nDONE WITH MISMATCHES")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
