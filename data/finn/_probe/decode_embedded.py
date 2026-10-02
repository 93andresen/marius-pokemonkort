#!/usr/bin/env python3
"""Probe: decode the embedded JSON payloads from a saved FINN search page.

FINN embeds several ``<script type="application/json">`` blocks whose bodies are
base64-encoded JSON (``data-props``, ``data-react-query-state``, ``data-podlets``,
``data-props`` …). This dumps each one, decoded, so we can learn the real shape.

Usage:  uv run data/finn/_probe/decode_embedded.py <saved.html> [outdir]
"""
from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

SCRIPT_RE = re.compile(r'<script type="application/json"([^>]*)>(.*?)</script>', re.S)
B64_RE = re.compile(r'[A-Za-z0-9+/]+={0,2}')


def try_decode(body: str) -> tuple[str, str | None]:
    """Return (decoded_text, how) — base64-decoded if it looks like base64."""
    stripped = body.strip()
    if stripped and B64_RE.fullmatch(stripped):
        try:
            raw = base64.b64decode(stripped, validate=True)
            text = raw.decode("utf-8")
            # sanity: must start with a JSON-ish char
            if text.lstrip()[:1] in "{[":
                return text, "base64"
        except Exception:
            pass
    return stripped, None


def main() -> int:
    html = Path(sys.argv[1]).read_text(encoding="utf-8")
    outdir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(sys.argv[1]).parent
    outdir.mkdir(parents=True, exist_ok=True)

    count = 0
    for i, m in enumerate(SCRIPT_RE.finditer(html)):
        attrs = m.group(1).strip()
        text, how = try_decode(m.group(2))
        count += 1
        label = re.sub(r'[^A-Za-z0-9_.-]+', "_", attrs).strip("_") or f"script{i:02d}"
        print("=" * 90)
        print(f"[{i:02d}] attrs={attrs!r}  decoded_via={how}  chars={len(text)}")

        # If it's JSON, pretty-print top-level keys + a small preview.
        parsed = None
        try:
            parsed = json.loads(text)
        except Exception as exc:  # noqa: BLE001 - we want to see failures
            print(f"     (not valid JSON: {exc})")
            print("     preview:", text[:600])
            continue

        out = outdir / f"embedded_{i:02d}_{label}.json"
        out.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        if isinstance(parsed, dict):
            print("     top-level keys:", list(parsed.keys()))
        elif isinstance(parsed, list):
            print(f"     list of {len(parsed)} items; item0 keys:",
                  list(parsed[0].keys()) if parsed and isinstance(parsed[0], dict) else type(parsed[0]).__name__ if parsed else "empty")
        print(f"     wrote -> {out}")

    print("=" * 90)
    print(f"decoded {count} embedded JSON script blocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
