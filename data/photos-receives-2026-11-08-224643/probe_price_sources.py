#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///
"""Probe each candidate sealed-product price source with exactly ONE request.

Test product: Eevee Heroes booster box (Japanese) -- the most expensive line in
offer.json, so it is the easiest thing to spot in a result page.

Prints status, final URL, size, page title and counts of yen/USD-looking tokens
so we can judge which sources are actually usable. Read-only reconnaissance:
nothing is written to disk.
"""

from __future__ import annotations

import re
import sys

import httpx

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

SOURCES: list[tuple[str, str]] = [
    (
        "pricecharting",
        "https://www.pricecharting.com/search-products?q=eevee+heroes+booster+box&type=prices",
    ),
    (
        "cardmarket",
        "https://www.cardmarket.com/en/Pokemon/Products/Search?searchString=Eevee+Heroes+Booster+Box",
    ),
    (
        "yuyutei",
        "https://yuyu-tei.jp/sell/poc/s/search?search_word="
        "%E3%82%A4%E3%83%BC%E3%83%96%E3%82%A4%E3%83%92%E3%83%BC%E3%83%AD%E3%83%BC%E3%82%BA",
    ),
    ("snkrdunk", "https://snkrdunk.com/en/search?keyword=eevee%20heroes"),
    (
        "mercari",
        "https://jp.mercari.com/search?keyword="
        "%E3%82%A4%E3%83%BC%E3%83%96%E3%82%A4%E3%83%92%E3%83%BC%E3%83%AD%E3%83%BC%E3%82%BA",
    ),
    (
        "tcgplayer",
        "https://www.tcgplayer.com/search/pokemon/product?q=eevee+heroes+booster+box",
    ),
    ("ebay", "https://www.ebay.com/sch/i.html?_nkw=eevee+heroes+booster+box"),
]

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
YEN_RE = re.compile(r"[¥￥]\s?[\d,]{3,}")
USD_RE = re.compile(r"\$\s?[\d,]+\.\d{2}")


def probe(name: str, url: str) -> None:
    print(f"\n=== {name} ===")
    print(f"GET {url}")
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=25.0,
            headers={
                "User-Agent": UA,
                "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
                "Accept": "text/html,application/xhtml+xml",
            },
        ) as client:
            resp = client.get(url)
    except Exception as exc:  # noqa: BLE001 - we want the reason, whatever it is
        print(f"  FAILED      : {type(exc).__name__}: {exc}")
        return

    body = resp.text
    match = TITLE_RE.search(body)
    title = re.sub(r"\s+", " ", match.group(1)).strip()[:90] if match else "(no title)"

    print(f"  status      : {resp.status_code}")
    print(f"  final_url   : {resp.url}")
    print(f"  bytes       : {len(resp.content)}")
    print(f"  content_type: {resp.headers.get('content-type')}")
    print(f"  title       : {title}")
    print(f"  yen_tokens  : {len(YEN_RE.findall(body))}")
    print(f"  usd_tokens  : {len(USD_RE.findall(body))}")
    print(f"  has_eevee   : {'eevee' in body.lower() or 'イーブイ' in body}")


def main() -> None:
    print(f"probing {len(SOURCES)} sources, one request each")
    for name, url in SOURCES:
        probe(name, url)
    print("\ndone")


if __name__ == "__main__":
    main()
    sys.exit(0)
