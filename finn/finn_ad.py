#!/usr/bin/env python3
"""FINN.no ad archive scraper — structured extraction, NO Markdown.

Given a FINN-kode (or any FINN link), this fetches the ad page once, stores the
**raw HTML as an immutable source**, and derives the machine-read fields (spec
``scraper-parser-spec.md`` §2.1) directly from the page's stable anchors:

  * ``finn_kode``      — canonical link, cross-checked against the ``FINN-kode``
                         line and the map link's ``adId`` (mismatch = loud error)
  * ``title``          — ``<h1 data-testid="object-title">``
  * ``status``         — the badge after the title (``Inaktiv`` / ``Solgt`` /
                         absent = ``Aktiv``) — status is as valuable as price
  * ``price_nok``      — the amount next to ``Til salgs`` / ``Til leie`` /
                         ``Gis bort``
  * ``lat``/``lon``/``postal_code`` — the map link query params (never geocoded)
  * ``location_text``  — ``data-testid="object-address"``
  * ``last_modified``  — ``Sist endret: D.M.YYYY kl. HH:MM`` (Norwegian format)
  * ``gallery_count``  — ``(n/m)`` from the gallery header, cross-checked against
                         the number of gallery image UUIDs (mismatch = loud error)
  * image UUIDs        — derived from the URL pattern, not by clicking the gallery
  * ``description_raw``— the ``data-testid="description"`` blob (immutable text)

Layout (spec §1.4, adapted for the §0.5 pivot: JSON/HTML instead of Markdown)::

    data/finn/annonser/{kode}_{slug}/
        raw/{kode}_{ts}.html        immutable source, one file per scrape event
        photos/{NN}_{uuid}.jpg      max-resolution images (idempotent: uuid-named)
        {kode}.json                 latest parsed machine-read record ("view")
        manifest.json               index: identity, scrapes[] (append-only),
                                    images[] (uuid/size/bytes/sha1), similar_ads
    data/finn/_log/ad_scrapes.jsonl append-only global log (one row per scrape)

Notes
-----
* Max image resolution: ``original`` is the true largest token (verified
  2026-10-02: ``original`` 1 940 757 B > ``1600w`` 716 169 B > ``1280w`` 358 317 B;
  ``2000w`` → 404). Downloads try ``original`` → ``1600w`` → ``1280w`` → ``960w``
  and step down on a 404, so a missing original never breaks the archive.
* Nothing is ever deleted or overwritten: raw captures get a fresh timestamped
  name, images are uuid-named and skipped only when already present with a
  non-zero size.

Examples
--------
  # One ad from a kode or any link form:
  uv run finn/finn_ad.py 475878513
  uv run finn/finn_ad.py "https://www.finn.no/recommerce/forsale/item/475878513?ci=20"

  # Never download images (fields only):
  uv run finn/finn_ad.py 475878513 --no-images

  # Parse an already-saved page offline (still writes the archive, no network):
  uv run finn/finn_ad.py --parse data/finn/_probe/ad_475878513.html

  # Scrape every kode found in a search run's combined JSONL:
  uv run finn/finn_ad.py --from-jsonl data/finn/searches/<run>/all_ads.jsonl

  # Scrape every kode in the discovery registry (a JSON object keyed by kode):
  uv run finn/finn_ad.py --from-registry data/finn/registry/pokemon-kort.json
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import finnlib as fl  # noqa: E402  (local sibling module)

PARSER_VERSION = "finn_ad/1.0.0"

TRADE_LABELS = ["Til salgs", "Til leie", "Gis bort", "Ønskes kjøpt", "Auksjon"]
STATUS_WORDS = ["Solgt", "Inaktiv", "Aktiv", "Reservert"]

_RE_TITLE = re.compile(r'<h1[^>]*data-testid="object-title"[^>]*>(.*?)</h1>', re.S | re.I)
_RE_TITLE_ANY = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
_RE_BADGE = re.compile(r'class="badge--[^"]*"[^>]*>\s*([^<]+?)\s*</div>', re.I)
_RE_TRADE = re.compile(
    r">\s*(" + "|".join(map(re.escape, TRADE_LABELS)) + r")\s*</\w+>\s*<\w[^>]*>\s*([^<]*?)\s*</", re.I
)
_RE_LAST_MOD = re.compile(
    r"Sist endret[^0-9]{0,40}(\d{1,2}\.\d{1,2}\.\d{4})\s*kl\.\s*(\d{1,2}:\d{2})", re.I
)
_RE_FINNKODE_LINE = re.compile(r"FINN-kode[^0-9]{0,40}(\d{6,})", re.I)
_RE_CANONICAL = re.compile(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', re.I)
_RE_OBJECT_ADDR = re.compile(r'<span[^>]*data-testid="object-address"[^>]*>(.*?)</span>', re.S | re.I)
_RE_MAPLINK = re.compile(
    r'href="[^"]*?/map\?(?:[^"]*?)adId=(\d{6,})(?:[^"]*?)lat=(-?[\d.]+)(?:[^"]*?)lon=(-?[\d.]+)'
    r'(?:[^"]*?)postalCode=(\d{3,5})',
    re.I,
)
_RE_MAPLINK_NOPC = re.compile(r'adId=(\d{6,})[^"]*?lat=(-?[\d.]+)[^"]*?lon=(-?[\d.]+)', re.I)
_RE_GALLERY_COUNT = re.compile(r"\((\d{1,3})\s*/\s*(\d{1,3})\)")
_RE_DESC_SECTION = re.compile(r'data-testid="description"[^>]*>(.*?)</section>', re.S | re.I)
_RE_DESC_PREWRAP = re.compile(r'class="whitespace-pre-wrap">(.*?)</div>', re.S | re.I)
_RE_BREADCRUMB = re.compile(r"<w-breadcrumb-item[^>]*>(.*?)</w-breadcrumb-item>", re.S | re.I)
_RE_IMG = re.compile(r"images\.finncdn\.no/dynamic/([^/\"'\\ ]+)/+item/(\d+)/([0-9a-fA-F-]{36})")
_RE_CONDITION = re.compile(r"Tilstand[^<]{0,20}<[^>]*>(.*?)<", re.S | re.I)
# The description DOM node appends a "show full description" UI control; the
# real description ends right before it. Split once and keep the part before.
_DESC_UI_MARKER = re.compile(r"Vis hele beskrivelsen|NB:\s*Knappen for", re.I)


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #


def _first(match: re.Match | None) -> str | None:
    if not match:
        return None
    return fl.strip_tags(match.group(1)).strip() or None


def _parse_nok(text: str | None) -> int | None:
    """Parse a NOK amount like ``1 200 kr`` / ``1.200,-`` into an int."""
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None
    return int(digits)


def _parse_norwegian_datetime(date_s: str, time_s: str) -> str | None:
    """``8.9.2026`` + ``18:44`` → ``2026-09-08T18:44:00`` (Europe/Oslo local)."""
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%y %H:%M", "%d.%m.%Y %H.%M"):
        try:
            return datetime.strptime(f"{date_s} {time_s}", fmt).isoformat()
        except ValueError:
            continue
    return None


def extract_gallery_images(html: str, kode: str) -> list[dict[str, str]]:
    """Return the ad's own gallery images as ``[{uuid, item_ref, base_url}]``.

    Derives image URLs from the UUID pattern (spec §1.2) and keeps only entries
    whose ``item_ref`` equals the ad's own kode, so "Mer som dette" thumbnails
    (other ads) are excluded. De-duplicated by uuid, first occurrence order.
    """
    seen: dict[str, dict[str, str]] = {}
    for m in _RE_IMG.finditer(html):
        size, ref, uuid = m.group(1), m.group(2), m.group(3).lower()
        if ref != kode:
            continue
        if uuid in seen:
            continue
        seen[uuid] = {
            "uuid": uuid,
            "item_ref": ref,
            "base_url": f"https://images.finncdn.no/dynamic/{size}/item/{ref}/{uuid}",
        }
    return list(seen.values())


def extract_similar_ads(html: str) -> list[dict[str, Any]]:
    """Return the "Mer som dette" (recommendations) items — already in the page."""
    out: list[dict[str, Any]] = []
    for props in fl.extract_data_props(html):
        recs = props.get("recommendationsData")
        if not isinstance(recs, dict):
            continue
        for it in recs.get("items") or []:
            iid = str(it.get("itemId") or "")
            if not iid or iid.startswith("advertising"):
                continue  # skip the ad slot placeholder
            out.append({
                "item_id": iid,
                "heading": it.get("heading"),
                "price_label": it.get("label"),
                "location": (it.get("location") or {}).get("combined"),
                "categories": it.get("categories"),
                "disposed_text": (it.get("disposed") or {}).get("text"),
                "disposed_value": (it.get("disposed") or {}).get("value"),
                "type_label": it.get("typeLabel"),
                "url": "https://www.finn.no" + (it.get("url") or ""),
            })
    return out


def parse_ad(html: str, *, kode_hint: str | None = None) -> dict[str, Any]:
    """Parse a FINN ad page into a machine-read record (spec §2.1)."""
    result: dict[str, Any] = {"parser_version": PARSER_VERSION, "parsed_at": fl.iso_now()}
    missing: list[str] = []
    warnings: list[str] = []

    # --- identity (kode) with cross-checks ---
    candidates: dict[str, str] = {}
    m = _RE_CANONICAL.search(html)
    if m:
        ck = fl.canonical_kode(m.group(1))
        if ck:
            candidates["canonical"] = ck
    m = _RE_FINNKODE_LINE.search(html)
    if m:
        candidates["object_info"] = m.group(1)
    m = _RE_MAPLINK.search(html) or _RE_MAPLINK_NOPC.search(html)
    if m:
        candidates["maplink"] = m.group(1)
    for b in fl.extract_embedded_json(html):
        if "contact-button" in (b.get("attrs") or "") and isinstance(b.get("data"), dict):
            cb = b["data"]
            if cb.get("adId"):
                candidates["contact_button"] = str(cb["adId"])
            result["contact_button"] = {
                "adId": cb.get("adId"), "segment": cb.get("segment"),
                "type": cb.get("type"), "name": cb.get("name"),
            }
    if kode_hint:
        candidates["hint"] = kode_hint

    kodes = set(candidates.values())
    if len(kodes) == 1:
        result["finn_kode"] = kodes.pop()
    elif kodes:
        warnings.append(f"FINN-kode disagreement across anchors: {candidates}")
        result["finn_kode"] = (kode_hint or max(kodes, key=len))
    else:
        result["finn_kode"] = kode_hint
        missing.append("finn_kode")
    result["kode_candidates"] = candidates

    # --- title + status ---
    title = _first(_RE_TITLE.search(html)) or _first(_RE_TITLE_ANY.search(html))
    result["title"] = title
    if not title:
        missing.append("title")

    status = "Aktiv"
    if title:
        m = _RE_TITLE.search(html) or _RE_TITLE_ANY.search(html)
        window = html[m.end(): m.end() + 400] if m else ""
        bm = _RE_BADGE.search(window)
        if bm:
            badge = fl.strip_tags(bm.group(1)).strip()
            for w in STATUS_WORDS:
                if w.lower() in badge.lower():
                    status = w
                    break
    result["status"] = status

    # --- trade type + price ---
    tm = _RE_TRADE.search(html)
    if tm:
        result["trade_type"] = tm.group(1)
        price_raw = fl.strip_tags(tm.group(2)).strip()
        result["price_label"] = price_raw
        if "gis bort" in tm.group(1).lower():
            result["price_nok"] = 0
        else:
            result["price_nok"] = _parse_nok(price_raw)
    else:
        result["trade_type"] = None
        result["price_label"] = None
        result["price_nok"] = None
        missing.append("price_nok")

    # --- location / coordinates ---
    result["location_text"] = _first(_RE_OBJECT_ADDR.search(html))
    mm = _RE_MAPLINK.search(html) or _RE_MAPLINK_NOPC.search(html)
    if mm:
        result["lat"] = float(mm.group(2))
        result["lon"] = float(mm.group(3))
        result["postal_code"] = mm.group(4) if mm.re is _RE_MAPLINK else None
    else:
        result["lat"] = result["lon"] = result["postal_code"] = None
        missing.append("coordinates")

    # --- last modified (ad's own timestamp, distinct from scrape time) ---
    lm = _RE_LAST_MOD.search(html)
    if lm:
        result["last_modified_raw"] = f"{lm.group(1)} kl. {lm.group(2)}"
        result["last_modified"] = _parse_norwegian_datetime(lm.group(1), lm.group(2))
    else:
        result["last_modified_raw"] = None
        result["last_modified"] = None
        missing.append("last_modified")

    # --- gallery count + images ---
    gc = _RE_GALLERY_COUNT.search(html)
    result["gallery_count"] = int(gc.group(2)) if gc else None
    kode = result.get("finn_kode") or ""
    images = extract_gallery_images(html, kode) if kode else []
    result["image_uuids"] = [im["uuid"] for im in images]
    result["image_count_from_html"] = len(images)
    if not gc:
        missing.append("gallery_count")

    # --- description (immutable raw blob) ---
    desc = _first(_RE_DESC_SECTION.search(html)) or _first(_RE_DESC_PREWRAP.search(html))
    if desc:
        # Trim the trailing "show full description" UI control, keep the text.
        desc = _DESC_UI_MARKER.split(desc, maxsplit=1)[0].strip() or None
    result["description_raw"] = desc
    if not desc:
        missing.append("description_raw")

    # --- breadcrumbs ---
    result["breadcrumbs"] = [
        fl.strip_tags(b).strip() for b in _RE_BREADCRUMB.findall(html) if fl.strip_tags(b).strip()
    ]

    # --- optional fields: absence is itself data (spec §2.1) ---
    cond = _RE_CONDITION.search(html)
    result["condition"] = fl.strip_tags(cond.group(1)).strip() if cond else None
    # These are genuinely optional / JS-only; None means "not present here".
    result["favorite_count"] = None  # JS-only anchor; not in server HTML
    result["similar_ads"] = extract_similar_ads(html)

    # --- cross-checks: a mismatch is a loud error, never a silent pick ---
    if result["gallery_count"] is not None and images:
        if result["gallery_count"] != len(images):
            warnings.append(
                f"gallery_count ({result['gallery_count']}) != image uuids ({len(images)})"
            )

    result["missing_fields"] = missing
    # parse_quality: failed if we got no identity/title; full if no anchor missed.
    if not result.get("finn_kode") or not title:
        result["parse_quality"] = "failed"
    elif missing:
        result["parse_quality"] = "partial"
    else:
        result["parse_quality"] = "full"
    result["warnings"] = warnings
    result["image_candidates"] = images
    return result


# --------------------------------------------------------------------------- #
# image download
# --------------------------------------------------------------------------- #


def existing_image_for(folder: Path, uuid: str) -> Path | None:
    """Return an on-disk photo for ``uuid`` if present with non-zero size."""
    photos = folder / "photos"
    if not photos.is_dir():
        return None
    for p in photos.glob(f"*{uuid}*"):
        if p.is_file() and p.stat().st_size > 0:
            return p
    return None


def download_one_image(base_url: str, dest: Path, *, verbose: bool = True) -> dict[str, Any]:
    """Download ``base_url`` at the largest working size. Returns a result dict.

    Tries the size tokens largest-first and steps down on 404. Verifies the
    response is an image with a non-zero body before writing (spec §1.2).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_err = None
    for size_url in fl.image_url_variants(base_url):
        m = re.search(r"/dynamic/([^/]+)/item/", size_url)
        size = m.group(1) if m else "?"
        try:
            status, body, headers = fl.http_get(size_url, timeout=60, retries=2, verbose=verbose)
        except Exception as exc:  # noqa: BLE001 - FetchError after retries
            last_err = f"{size_url}: {exc}"
            continue
        ctype = (headers.get("content-type") or "").lower()
        if status == 404 or status == 403:
            last_err = f"HTTP {status} for {size_url}"
            continue
        if status != 200:
            last_err = f"HTTP {status} for {size_url}"
            continue
        if not ctype.startswith("image/"):
            last_err = f"non-image content-type {ctype!r} for {size_url}"
            continue
        if len(body) == 0:
            last_err = f"zero-byte body for {size_url}"
            continue
        # Overwrite-safe write (never clobber an existing file).
        target = fl.unique_path(dest)
        target.write_bytes(body)
        return {
            "ok": True, "size": size, "url": size_url, "file": target.name,
            "bytes": len(body), "content_type": ctype, "sha1": fl.sha1_hex(body),
        }
    return {"ok": False, "error": last_err or "unknown download failure", "url": base_url}


# --------------------------------------------------------------------------- #
# archive
# --------------------------------------------------------------------------- #


def find_existing_ad_dir(root: Path, kode: str) -> Path | None:
    if not root.is_dir():
        return None
    for p in root.iterdir():
        if p.is_dir() and (p.name == kode or p.name.startswith(f"{kode}_")):
            return p
    return None


def ad_dir_for(root: Path, kode: str, title: str | None) -> tuple[Path, bool]:
    """Return ``(folder, is_new)`` for an ad; reuse the existing folder if any."""
    existing = find_existing_ad_dir(root, kode)
    if existing:
        return existing, False
    slug = fl.slugify(title or "annonse")
    folder = root / f"{kode}_{slug}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder, True


def load_manifest(folder: Path) -> dict[str, Any]:
    p = folder / "manifest.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"    WARNING: manifest unreadable ({exc!r}); starting a fresh view")
    return {}


def scrape_ad(
    *,
    kode_hint: str | None,
    url: str | None,
    html: str | None,
    root: Path,
    log_dir: Path,
    download_images: bool,
    max_images: int | None,
    force_images: bool,
    delay: float,
    jitter: float,
    verbose: bool = True,
) -> dict[str, Any]:
    """Archive one ad: raw capture + parsed fields + images + manifest."""
    source = url or (fl.ITEM_URL_TMPL.format(kode=kode_hint) if kode_hint else None)
    print("\n" + "-" * 88)
    print(f"AD {kode_hint}  <- {source or '(offline parse)'}")

    if html is None:
        if not source:
            raise ValueError("need a url (or kode_hint) when no html is supplied")
        status, body, _h = fl.http_get(source, retries=3, base_delay=delay, jitter=jitter)
        html = body.decode("utf-8", errors="replace")
        print(f"    fetched {len(html)} chars (HTTP {status})")

    parsed = parse_ad(html, kode_hint=kode_hint)
    kode = parsed.get("finn_kode") or kode_hint or "unknown"
    print(f"    kode={kode}  title={parsed.get('title')!r}")
    print(f"    status={parsed.get('status')}  trade={parsed.get('trade_type')}  "
          f"price={parsed.get('price_nok')}  gallery={parsed.get('gallery_count')}")
    print(f"    quality={parsed.get('parse_quality')}  missing={parsed.get('missing_fields')}")
    for w in parsed.get("warnings") or []:
        print(f"    WARNING: {w}")

    folder, is_new = ad_dir_for(root, kode, parsed.get("title"))
    print(f"    folder{' (new)' if is_new else ' (existing)'}: {folder}")

    # 1. immutable raw capture (fresh timestamped name — never overwritten)
    ts = fl.ts_now()
    raw_dir = fl.ensure_dir(folder / "raw")
    raw_path = fl.unique_path(raw_dir / f"{kode}_{ts}.html")
    raw_path.write_text(html, encoding="utf-8")
    print(f"    raw  -> {raw_path.relative_to(root)}  ({len(html)} chars)")
    parsed["raw_capture"] = str(raw_path.relative_to(root)).replace("\\", "/")

    # 2. images (max resolution, uuid-named → idempotent)
    images_meta: list[dict[str, Any]] = []
    candidates = parsed.get("image_candidates") or []
    if download_images:
        todo = candidates if max_images is None else candidates[:max_images]
        print(f"    downloading {len(todo)}/{len(candidates)} images (max-res) …")
        for idx, im in enumerate(todo, start=1):
            uuid = im["uuid"]
            existing = None if force_images else existing_image_for(folder, uuid)
            if existing:
                st = existing.stat()
                images_meta.append({
                    "index": idx, "uuid": uuid, "item_ref": im["item_ref"],
                    "file": f"photos/{existing.name}", "bytes": st.st_size,
                    "skipped": "already-present",
                })
                print(f"      [{idx:02d}/{len(todo)}] {uuid}  skip (already present)")
                continue
            dest = folder / "photos" / f"{idx:02d}_{uuid}.jpg"
            res = download_one_image(im["base_url"], dest, verbose=verbose)
            if res.get("ok"):
                print(f"      [{idx:02d}/{len(todo)}] {uuid}  {res['size']}  "
                      f"{res['bytes']} B  -> {res['file']}")
                images_meta.append({"index": idx, **im, **{k: v for k, v in res.items() if k != "file"},
                                    "file": f"photos/{res['file']}"})
            else:
                print(f"      [{idx:02d}/{len(todo)}] {uuid}  FAILED: {res.get('error')}")
                images_meta.append({"index": idx, **im, "ok": False, "error": res.get("error")})
            time.sleep(delay + random.uniform(0, jitter))
    else:
        print("    images: skipped (--no-images)")

    ok_count = sum(1 for i in images_meta if i.get("ok") or i.get("skipped"))
    if download_images and images_meta and ok_count != len(images_meta):
        print(f"    WARNING: {len(images_meta) - ok_count} image(s) failed to archive")

    # 3. parsed record: per-scrape immutable copy + latest "view"
    parsed_dir = fl.ensure_dir(folder / "parsed")
    parsed_path = fl.unique_path(parsed_dir / f"{kode}_{ts}.json")
    fl.write_json(parsed_path, parsed)
    fl.write_json(folder / f"{kode}.json", parsed)

    # 4. manifest (index; scrapes[] is append-only)
    manifest = load_manifest(folder)
    manifest.setdefault("finn_kode", kode)
    manifest["url"] = source or fl.ITEM_URL_TMPL.format(kode=kode)
    manifest["slug"] = folder.name
    manifest["first_seen"] = manifest.get("first_seen") or parsed["parsed_at"]
    manifest["last_seen"] = parsed["parsed_at"]
    manifest["parser_version"] = PARSER_VERSION
    manifest["latest"] = {
        "title": parsed.get("title"), "status": parsed.get("status"),
        "price_nok": parsed.get("price_nok"), "trade_type": parsed.get("trade_type"),
        "location_text": parsed.get("location_text"), "postal_code": parsed.get("postal_code"),
        "last_modified": parsed.get("last_modified"), "gallery_count": parsed.get("gallery_count"),
        "parse_quality": parsed.get("parse_quality"),
    }
    manifest.setdefault("scrapes", []).append({
        "scraped_at": parsed["parsed_at"], "raw": parsed["raw_capture"],
        "parse_quality": parsed.get("parse_quality"), "price_nok": parsed.get("price_nok"),
        "status": parsed.get("status"), "missing_fields": parsed.get("missing_fields"),
        "warnings": parsed.get("warnings"),
    })
    # merge images by uuid (never drop a previously archived image)
    by_uuid = {im["uuid"]: im for im in manifest.get("images", []) if im.get("uuid")}
    for im in images_meta:
        by_uuid[im["uuid"]] = im
    manifest["images"] = [by_uuid[k] for k in sorted(by_uuid)]
    manifest["image_count_on_disk"] = sum(
        1 for p in (folder / "photos").glob("*") if p.is_file() and p.stat().st_size > 0
    ) if (folder / "photos").is_dir() else 0
    manifest["similar_ads"] = parsed.get("similar_ads") or manifest.get("similar_ads") or []
    fl.write_json(folder / "manifest.json", manifest)

    # 5. global append-only log
    fl.append_jsonl(log_dir / "ad_scrapes.jsonl", {
        "scraped_at": parsed["parsed_at"], "finn_kode": kode, "url": manifest["url"],
        "title": parsed.get("title"), "status": parsed.get("status"),
        "price_nok": parsed.get("price_nok"), "gallery_count": parsed.get("gallery_count"),
        "parse_quality": parsed.get("parse_quality"), "images_ok": ok_count,
        "images_total": len(images_meta), "missing_fields": parsed.get("missing_fields"),
        "warnings": parsed.get("warnings"), "folder": str(folder),
    })
    print(f"    done: manifest={folder / 'manifest.json'}")
    return {"kode": kode, "folder": str(folder), "parsed": parsed, "images": images_meta}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _load_kodes_from(jsonl_path: Path) -> list[str]:
    kodes: list[str] = []
    # JSONL is "\n"-delimited: splitlines() breaks on U+2028/U+2029 too, which
    # would split a row and silently drop its kode.
    for line in jsonl_path.read_text(encoding="utf-8").split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            k = obj.get("finn_kode") or obj.get("ad_id") or obj.get("id")
        except Exception:  # noqa: BLE001 - not JSON: treat the whole line as a link/kode
            k = line
        kk = fl.canonical_kode(str(k)) if k else None
        if kk and kk not in kodes:
            kodes.append(kk)
    return kodes


def load_registry_kodes(path: Path) -> list[str]:
    """Return the FINN-koder from a discovery registry JSON object (keys).

    ``data/finn/registry/pokemon-kort.json`` is a JSON *object* keyed by kode, so
    it cannot be read by :func:`_load_kodes_from` (which expects JSONL rows). Keys
    that are not a valid kode are ignored; the result is de-duplicated and sorted
    so the scrape order is deterministic. A missing file yields ``[]`` (the caller
    turns that into a loud error).
    """
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    kodes: list[str] = []
    for key in data:
        kk = fl.canonical_kode(str(key))
        if kk and kk not in kodes:
            kodes.append(kk)
    return sorted(kodes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("targets", nargs="*", metavar="KODE_OR_URL",
                        help="one or more FINN-koder and/or links")
    parser.add_argument("--from-jsonl", metavar="FILE",
                        help="also read koder from a JSONL file (e.g. a search run's all_ads.jsonl)")
    parser.add_argument("--from-registry", metavar="FILE",
                        help="also read koder from a registry JSON object (keys are FINN-koder)")
    parser.add_argument("--outdir", default=str(fl.DATA_FINN / "annonser"),
                        help="archive root (default data/finn/annonser)")
    parser.add_argument("--parse", metavar="HTML",
                        help="offline: parse this saved ad HTML instead of fetching (single target)")
    parser.add_argument("--no-images", action="store_true", help="do not download images")
    parser.add_argument("--max-images", type=int, default=None, help="download at most N images")
    parser.add_argument("--force-images", action="store_true", help="re-download even if present")
    parser.add_argument("--delay", type=float, default=1.0, help="base delay between requests (s)")
    parser.add_argument("--jitter", type=float, default=0.8, help="random jitter added to delay (s)")
    parser.add_argument("--dry-run", action="store_true", help="show what would be scraped; do nothing")
    parser.add_argument("--json", action="store_true", help="print the full parsed record(s) as JSON")
    args = parser.parse_args(argv)

    root = Path(args.outdir)
    log_dir = fl.ensure_dir(fl.DATA_FINN / "_log")

    # ---- offline parse mode ----
    if args.parse:
        html = Path(args.parse).read_text(encoding="utf-8")
        hint = fl.canonical_kode(args.parse) or (args.targets[0] if args.targets else None)
        if hint:
            hint = fl.canonical_kode(hint) or hint
        res = scrape_ad(
            kode_hint=hint, url=None, html=html, root=root, log_dir=log_dir,
            download_images=not args.no_images, max_images=args.max_images,
            force_images=args.force_images, delay=args.delay, jitter=args.jitter,
        )
        if args.json:
            print(json.dumps(res["parsed"], ensure_ascii=False, indent=2))
        return 0

    # ---- build target list ----
    kodes: list[str] = []
    for t in args.targets:
        kk = fl.canonical_kode(t)
        if not kk:
            print(f"ERROR: could not extract a FINN-kode from {t!r}")
            return 2
        if kk not in kodes:
            kodes.append(kk)
    if args.from_jsonl:
        for kk in _load_kodes_from(Path(args.from_jsonl)):
            if kk not in kodes:
                kodes.append(kk)
    if args.from_registry:
        reg_path = Path(args.from_registry)
        if not reg_path.exists():
            print(f"ERROR: registry not found: {reg_path}")
            return 2
        for kk in load_registry_kodes(reg_path):
            if kk not in kodes:
                kodes.append(kk)
    if not kodes:
        print("ERROR: no targets. Pass a kode/link or --from-jsonl FILE.")
        return 2

    print("=" * 88)
    print(f"FINN ad archive  |  {len(kodes)} ad(s)  |  outdir={root}  images={not args.no_images}")
    print("=" * 88)

    results = []
    for kode in kodes:
        if args.dry_run:
            print(f"  would scrape {kode} -> {fl.ITEM_URL_TMPL.format(kode=kode)}")
            continue
        try:
            results.append(scrape_ad(
                kode_hint=kode, url=fl.ITEM_URL_TMPL.format(kode=kode), html=None,
                root=root, log_dir=log_dir, download_images=not args.no_images,
                max_images=args.max_images, force_images=args.force_images,
                delay=args.delay, jitter=args.jitter,
            ))
        except Exception as exc:  # noqa: BLE001 - log and keep going (never silently drop)
            print(f"  FAILED {kode}: {exc!r}")
            fl.append_jsonl(log_dir / "ad_scrapes.jsonl", {
                "scraped_at": fl.iso_now(), "finn_kode": kode, "error": repr(exc),
                "url": fl.ITEM_URL_TMPL.format(kode=kode),
            })
        time.sleep(args.delay + random.uniform(0, args.jitter))

    print("\n" + "=" * 88)
    print(f"DONE  archived={len(results)}/{len(kodes)}")
    print("=" * 88)
    if args.json:
        print(json.dumps([r["parsed"] for r in results], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
