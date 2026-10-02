#!/usr/bin/env python3
"""Shared helpers for the FINN.no tooling (structured extraction, no Markdown).

Design (see ``scraper-parser-spec.md`` §0.5): a FINN page is a React app that
server-renders ``<script type="application/json" …>`` blocks whose bodies are
**base64-encoded JSON**. The authoritative, lossless payload — the full result
set, the complete filter/parameter map, pagination — lives in those blocks.

We therefore never convert a page to Markdown. We decode the embedded JSON,
store the **raw HTML** as an immutable source, and parse downstream from the
stored source (so a parser fix can always be re-run without re-fetching).

This module is dependency-free (stdlib only) and import-level side-effect free,
so both ``finn_search.py`` and ``finn_ad.py`` can share it.
"""
from __future__ import annotations

import base64
import hashlib
import html as _html
import json
import random
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# --- constants -------------------------------------------------------------

BASE_URL = "https://www.finn.no"
SEARCH_HTML_URL = BASE_URL + "/recommerce/forsale/search"
# FINN's own internal search JSON API (advertised in the page's embedded props).
SEARCH_API_URL = BASE_URL + "/recommerce/forsale/search/api"
ITEM_URL_TMPL = BASE_URL + "/recommerce/forsale/item/{kode}"
IMAGE_BASE = "https://images.finncdn.no/dynamic"

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nb-NO,nb;q=0.9,en;q=0.8",
}

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_FINN = REPO_ROOT / "data" / "finn"

# The size token used in FINN image URLs; the API returns "/default/" but the
# CDN serves a range of sizes. Verified 2026-10-02 against a live ad:
#   original -> HTTP 200 (1 940 757 bytes)   <- TRUE MAXIMUM
#   1600w    -> HTTP 200 (   716 169 bytes)
#   1280w    -> HTTP 200 (   358 317 bytes)
#   960w / 640w / 480x480c / 320w / 142w -> smaller
#   2000w    -> HTTP 404
# ``original`` is therefore the max-resolution token for downloads.
IMAGE_SIZE_DEFAULT = "default"
IMAGE_SIZE_MAX = "1280w"  # safe token for *record* URLs (always resolvable)
IMAGE_SIZE_ORIGINAL = "original"
# Download fallback chain, largest first. If a token 404s we step down.
IMAGE_SIZE_FALLBACKS = ["original", "1600w", "1280w", "960w"]

_SCRIPT_RE = re.compile(
    r'<script\b([^>]*?)\btype="application/json"([^>]*)>(.*?)</script>',
    re.S | re.I,
)
_B64_RE = re.compile(r"[A-Za-z0-9+/]+={0,2}")
# ``<div … data-props=BASE64>`` — podlets embed their props this way (base64 JSON).
_DATA_PROPS_RE = re.compile(r"data-props=([A-Za-z0-9+/=]{20,})")


# --- small utilities -------------------------------------------------------


def ts_now() -> str:
    """Return a filename-safe UTC timestamp: ``YYYY-MM-DD-HHMMSS``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")


def iso_now() -> str:
    """Return an ISO-8601 UTC timestamp with trailing ``Z``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(value: Any, maxlen: int = 60) -> str:
    """Turn arbitrary text into a safe, lowercase, dash-separated slug."""
    text = re.sub(r"[^A-Za-z0-9]+", "-", str(value)).strip("-").lower()
    return (text[:maxlen].rstrip("-")) or "x"


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_json(path: str | Path, obj: Any) -> Path:
    """Write ``obj`` as pretty UTF-8 JSON (creating parent dirs)."""
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def append_jsonl(path: str | Path, obj: Any) -> Path:
    """Append one JSON object as a line, flushed to disk immediately."""
    p = Path(path)
    ensure_dir(p.parent)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False))
        fh.write("\n")
        fh.flush()
    return p


def unique_path(path: str | Path) -> Path:
    """Return a non-existing path, appending ``-1``/``-2`` … if needed."""
    p = Path(path)
    if not p.exists():
        return p
    stem, suffix, parent = p.stem, p.suffix, p.parent
    i = 1
    while True:
        cand = parent / f"{stem}-{i}{suffix}"
        if not cand.exists():
            return cand
        i += 1


# --- HTTP (with visible retries) ------------------------------------------


class FetchError(RuntimeError):
    """Raised when a request ultimately fails after all retries."""


def http_get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    retries: int = 3,
    base_delay: float = 2.0,
    jitter: float = 1.5,
    verbose: bool = True,
) -> tuple[int, bytes, dict[str, str]]:
    """GET ``url``, retrying transient failures with exponential backoff.

    Returns ``(status, body_bytes, headers)``. Raises :class:`FetchError` only
    after every attempt has failed — never silently swallows an error.
    """
    merged = dict(DEFAULT_HEADERS)
    if headers:
        merged.update(headers)

    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, headers=merged, method="GET")
        started = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                hdrs = {k.lower(): v for k, v in resp.headers.items()}
                if verbose:
                    print(
                        f"    GET {url} -> {resp.status} "
                        f"({len(body)} bytes, {time.time() - started:.2f}s)"
                    )
                return resp.status, body, hdrs
        except urllib.error.HTTPError as exc:  # a real HTTP status
            body = exc.read()
            hdrs = {k.lower(): v for k, v in (exc.headers or {}).items()}
            if verbose:
                print(f"    GET {url} -> HTTP {exc.code} (attempt {attempt}/{retries})")
            # Do not retry client errors other than 429/503.
            if exc.code not in (429, 503) or attempt == retries:
                return exc.code, body, hdrs
            last_exc = exc
        except Exception as exc:  # noqa: BLE001 - network/JSON/etc; we log & retry
            last_exc = exc
            if verbose:
                print(f"    GET {url} -> error {exc!r} (attempt {attempt}/{retries})")
            if attempt == retries:
                break

        sleep_for = base_delay * (2 ** (attempt - 1)) + random.uniform(0, jitter)
        if verbose:
            print(f"    retrying in {sleep_for:.1f}s …")
        time.sleep(sleep_for)

    raise FetchError(f"GET {url} failed after {retries} attempts: {last_exc!r}")


# --- embedded-JSON extraction ---------------------------------------------


def _iter_json_scripts(html: str) -> Iterable[tuple[str, str]]:
    """Yield ``(attrs, body)`` for every ``<script type="application/json">``."""
    for m in _SCRIPT_RE.finditer(html):
        attrs = (m.group(1) + " " + m.group(2)).strip()
        yield attrs, m.group(3)


def _decode_body(body: str) -> tuple[str, str | None]:
    """Base64-decode ``body`` if it looks like base64; return (text, how)."""
    stripped = body.strip()
    if stripped and _B64_RE.fullmatch(stripped):
        try:
            text = base64.b64decode(stripped, validate=True).decode("utf-8")
            if text.lstrip()[:1] in "{[":
                return text, "base64"
        except Exception:  # noqa: BLE001 - fall through to raw
            pass
    return stripped, None


def extract_embedded_json(html: str) -> list[dict[str, Any]]:
    """Return every embedded JSON block as ``{attrs, how, data}``.

    Blocks whose body is not valid JSON are still reported (with ``data=None``
    and a ``preview``) so a layout change is *visible*, never silently ignored.
    """
    out: list[dict[str, Any]] = []
    for attrs, body in _iter_json_scripts(html):
        text, how = _decode_body(body)
        entry: dict[str, Any] = {"attrs": attrs, "how": how}
        try:
            entry["data"] = json.loads(text)
        except Exception as exc:  # noqa: BLE001
            entry["data"] = None
            entry["error"] = f"{exc}"
            entry["preview"] = text[:400]
        out.append(entry)
    return out


def parse_search_state(html: str) -> dict[str, Any]:
    """Extract the search payload from a FINN search page's embedded JSON.

    Returns a dict with:
      * ``docs``      — list of ad documents for this page (may be empty)
      * ``metadata``  — pagination/filtering metadata (``paging``, ``num_results`` …)
      * ``filters``   — the complete machine-readable filter/parameter map
      * ``search_entry`` — the paid top placement, if present
      * ``query_state``  — the raw dehydrated React Query block that held ``docs``
      * ``blocks``    — count of embedded JSON blocks found (diagnostic)

    Raises :class:`ValueError` if no ``docs`` payload is found (layout change).
    """
    blocks = extract_embedded_json(html)
    docs: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] = {}
    filters: list[dict[str, Any]] = []
    query_state: dict[str, Any] | None = None
    search_entry: dict[str, Any] | None = None

    for blk in blocks:
        data = blk.get("data")
        if not isinstance(data, dict):
            continue
        for q in data.get("queries", []) or []:
            qdata = (q.get("state") or {}).get("data")
            if isinstance(qdata, dict) and "docs" in qdata:
                docs = qdata.get("docs")
                metadata = qdata.get("metadata") or {}
                filters = qdata.get("filters") or []
                query_state = q
            if isinstance(qdata, dict):
                entry = (qdata.get("result") or {}).get("searchEntry")
                if isinstance(entry, dict):
                    search_entry = entry

    if docs is None:
        raise ValueError(
            "no 'docs' payload found in embedded JSON — FINN layout may have "
            "changed. Inspect data/finn/_probe and update finnlib.parse_search_state."
        )

    return {
        "docs": docs,
        "metadata": metadata,
        "filters": filters,
        "search_entry": search_entry,
        "query_state": query_state,
        "blocks": len(blocks),
    }


def extract_data_props(html: str) -> list[dict[str, Any]]:
    """Decode every ``data-props=<base64>`` attribute value into JSON.

    Podlets (recommendations / suggestions / …) embed their props this way. The
    recommendations podlet carries the "Mer som dette" (similar-ads) payload,
    which is a useful comps source already present in every ad capture.
    """
    out: list[dict[str, Any]] = []
    for m in _DATA_PROPS_RE.finditer(html):
        try:
            obj = json.loads(base64.b64decode(m.group(1)).decode("utf-8"))
        except Exception:  # noqa: BLE001 - skip non-JSON props, keep going
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


# --- image URL handling ----------------------------------------------------


def image_url_size(url: str, size: str = IMAGE_SIZE_MAX) -> str:
    """Rewrite a FINN image URL to request a specific size token.

    ``https://images.finncdn.no/dynamic/default/item/…`` → ``…/dynamic/1280w/item/…``
    """
    return re.sub(r"(/dynamic/)[^/]+(/item/)", rf"\g<1>{size}\g<2>", url)


def max_image_urls(doc: dict[str, Any]) -> list[str]:
    """Return the ad's image URLs rewritten to the maximum size, de-duplicated."""
    urls: list[str] = []
    for u in doc.get("image_urls") or []:
        u = image_url_size(u)
        if u not in urls:
            urls.append(u)
    img = doc.get("image") or {}
    if img.get("url"):
        u = image_url_size(img["url"])
        if u not in urls:
            urls.insert(0, u)
    return urls


def image_url_variants(url: str, sizes: list[str] | None = None) -> list[str]:
    """Return ``url`` rewritten to each size token (largest first)."""
    return [image_url_size(url, s) for s in (sizes or IMAGE_SIZE_FALLBACKS)]


# --- text / id helpers -----------------------------------------------------


def strip_tags(frag: str) -> str:
    """Very small HTML→text: drops comments/tags, keeps line breaks, unescapes."""
    txt = re.sub(r"<!--.*?-->", "", frag, flags=re.S)
    txt = re.sub(r"<br\s*/?>", "\n", txt, flags=re.I)
    txt = re.sub(r"</(p|div|section|li|h[1-6])>", "\n\n", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", "", txt)
    return _html.unescape(txt)


def html_unescape(text: str) -> str:
    """Entity-decode a string."""
    return _html.unescape(text)


_KODE_PATTERNS = [
    r"/recommerce/forsale/item/(\d{6,})",
    r"/forsale/item/(\d{6,})",
    r"/item/(\d{6,})",
    r"[?&]adId=(\d{6,})",
    r"finn\.no/(\d{6,})",
    r"/(\d{6,})\b",
]


def canonical_kode(value: str) -> str | None:
    """Extract the FINN-kode (numeric ad id) from any input form (spec §1.1).

    Accepts a bare kode, a share link (``finn.no/475878513``), an address-bar
    link (``/recommerce/forsale/item/475878513``), a deep link (``?ci=20``) … .
    Returns ``None`` if no kode can be found.
    """
    if value is None:
        return None
    s = str(value).strip()
    if s.isdigit() and 6 <= len(s) <= 12:
        return s
    for pat in _KODE_PATTERNS:
        m = re.search(pat, s)
        if m:
            return m.group(1)
    return None


def sha1_hex(data: bytes) -> str:
    """Return the SHA-1 hex digest of ``data`` (image/capture integrity)."""
    return hashlib.sha1(data).hexdigest()
