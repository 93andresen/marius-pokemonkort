#!/usr/bin/env python3
"""Probe: learn the structure of a saved FINN *ad* page (vs the search page).

Usage:  uv run data/finn/_probe/probe_ad.py <saved_ad.html>
"""
from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "finn"))
import finnlib as fl  # noqa: E402


def main() -> int:
    path = Path(sys.argv[1])
    html = path.read_text(encoding="utf-8")
    print(f"file: {path}  ({len(html)} chars)")

    # 1. generic embedded JSON blocks (finnlib decoder: handles base64)
    print("\n=== finnlib.extract_embedded_json ===")
    try:
        blocks = fl.extract_embedded_json(html)
        print(f"{len(blocks)} block(s)")
        for i, b in enumerate(blocks):
            keys = list(b["data"].keys()) if isinstance(b.get("data"), dict) else type(b.get("data")).__name__
            print(f"  [{i}] how={b['how']!r} attrs={b['attrs'][:80]!r} keys={keys}")
    except Exception as exc:  # noqa: BLE001
        print("  ERROR:", exc)

    # 2. every <script ...> opening tag (attrs only)
    print("\n=== <script> opening tags (attrs) ===")
    for m in re.finditer(r"<script\b([^>]*)>", html, re.I):
        attrs = m.group(1).strip()
        print("  ", attrs[:140])

    # 3. data-props= blobs (base64 JSON)
    print("\n=== data-props= blobs ===")
    for i, m in enumerate(re.finditer(r"data-props=([A-Za-z0-9+/=]+)", html), 1):
        b64 = m.group(1)
        try:
            js = base64.b64decode(b64).decode("utf-8")
            obj = json.loads(js)
            keys = list(obj.keys()) if isinstance(obj, dict) else type(obj).__name__
            print(f"  #{i} {len(b64)} b64 chars -> keys={keys}")
            if isinstance(obj, dict) and obj.get("apiUrl"):
                print(f"       apiUrl={obj['apiUrl']}")
            # recommendations (Mer som dette) are a comps goldmine
            recs = (obj or {}).get("recommendationsData") if isinstance(obj, dict) else None
            if recs and isinstance(recs, dict):
                items = recs.get("items") or []
                print(f"       recommendations items={len(items)}")
                for it in items[:5]:
                    print(f"         - {it.get('itemId')}  {it.get('label')!r}  {it.get('heading')!r}  disposed={it.get('disposed')}")
        except Exception as exc:  # noqa: BLE001
            print(f"  #{i} decode failed: {exc!r}")

    # 4. data-testid values
    print("\n=== data-testid values ===")
    tids = sorted(set(re.findall(r'data-testid="([^"]+)"', html)))
    for t in tids:
        print("  ", t)

    # 5. image URLs (item/{ref}/{uuid}) unique
    print("\n=== image uuid/ref candidates ===")
    imgs = sorted(set(re.findall(r"/dynamic/[^/]+/item/(\d+)/([0-9a-f-]{36})", html)))
    print(f"  {len(imgs)} unique (itemRef,uuid) pairs")
    for ref, uuid in imgs[:8]:
        print(f"    ref={ref} uuid={uuid}")

    # 6. gallery count "(n/m)"
    print("\n=== gallery count ===")
    for m in re.finditer(r"\((\d+)\s*/\s*(\d+)\)", html):
        print("  ", m.group(0))

    # 7. key text regions
    print("\n=== keyword regions ===")
    for kw in ["Beskrivelse av varen", "Tilstand", "Sist endret", "FINN-kode",
               "Fiks ferdig", "Trygg betaling", "Frakt", "favoritt", "adId=",
               "coordinates", "postalCode", "\"adId\"", "Solgt", "Inaktiv"]:
        m = re.search(re.escape(kw), html)
        if not m:
            print(f"  [{kw}] NOT FOUND")
            continue
        s = max(0, m.start() - 100)
        snippet = re.sub(r"\s+", " ", html[s:s + 300])
        print(f"  [{kw}] @{m.start()}: {snippet}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
