#!/usr/bin/env python3
"""finn_matcher.py — match a FINN.no listing to PokeWallet cards + prices.

This is the engine behind the "goldmine": given a FINN heading (from the search
scraper ``all_ads.jsonl``) or a parsed ad (from ``finn_ad.py``), it works out
*what card the seller is actually selling* and overlays trustworthy PokeWallet
market prices on top of the FINN asking price — budget-capped and cached so it
never burns the 100 calls/hour free-plan quota.

What it produces (the "overlay payload", the JSON the browser tool consumes)::

    {
      "finn_kode": "477805681",
      "heading": "Psychic Energy #101 Base Set (1999)",
      "finn_price_nok": 9,
      "parsed": {"card_name": "Psychic Energy", "card_number": "101",
                 "set_hint": "Base Set", "year": 1999},
      "candidates": [ {pk_id, name, set_name, set_code, card_number, rarity,
                       price{}, score, flags[]} , ... ],
      "best": {...} | null,
      "value": {"source": "tcgplayer", "native": 0.14, "currency": "USD",
                "est_nok": 1, "finn_nok": 9, "delta_nok": 8,
                "fx_rate": 10.7, "estimated": true},
      "pricecharting_url": "https://www.pricecharting.com/... (unconfirmed)",
      "pricecharting_confirmed": false,
      "queries": ["Psychic Energy 101"],
      "calls_spent": 1, "cache_hit": false
    }

Design (mirrors the rest of the repo):
* **Structured, no scraping of Markdown.** Titles are parsed deterministically.
* **Never trust a free-text hit blindly** (D7): every candidate is *scored* on
  name + number + set signals; a low score is reported as such, never hidden.
* **Budget-aware + cached.** ``PokeWalletClient`` enforces the hourly/daily
  floors; successful queries are cached append-only (``_cache/``) and reused
  within ``--cache-hours`` so repeat lookups cost zero calls.
* **Nothing is overwritten:** matches are appended to ``matches.jsonl`` and each
  run also writes a timestamped ``overlay_<ts>.json``. PriceCharting links are
  stored but marked **unconfirmed** (a value is only "confirmed" when the user
  says so).

Examples
--------
  # One heading, offline (parse + plan queries only, no API calls):
  uv run finn/finn_matcher.py --heading "Psychic Energy #101 Base Set (1999)" --offline

  # One heading, live:
  uv run finn/finn_matcher.py --heading "Bronzor (Poke Ball Pattern) #066" --finn-price 10

  # Match every listing from a search run (capped at 20 API calls):
  uv run finn/finn_matcher.py --from-jsonl data/finn/searches/<run>/all_ads.jsonl --max-calls 20

  # Match a single archived ad:
  uv run finn/finn_matcher.py --ad-json data/finn/annonser/<slug>/<kode>.json
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- path setup: reuse finnlib (sibling) and pwlib (repo/pokewallet) ---------
_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent))                      # finn/  -> finnlib
sys.path.insert(0, str(_HERE.parents[1] / "pokewallet"))   # -> pwlib

import finnlib as fl  # noqa: E402  (local sibling module)
from pwlib import config as pwconfig  # noqa: E402
from pwlib import prices as pricelib  # noqa: E402
from pwlib import sets as setslib  # noqa: E402
from pwlib.api import BudgetExhausted, MissingApiKey, PokeWalletClient  # noqa: E402
from pwlib.util import append_jsonl, ensure_dir, now_ts, utc_iso  # noqa: E402

PARSER_VERSION = "finn_matcher/1.0.0"

MATCH_DIR: Path = fl.DATA_FINN / "matches"
CACHE_DIR: Path = fl.DATA_FINN / "_cache"
CACHE_JSONL: Path = CACHE_DIR / "query_cache.jsonl"
MATCH_JSONL: Path = MATCH_DIR / "matches.jsonl"

# Approximate FX rates (NOK per unit). These are *estimates*, clearly labelled as
# such in the output, and overridable with --fx-usd / --fx-eur. Update freely.
FX_DEFAULTS = {"USD": 10.70, "EUR": 11.60}

# --- heading parsing --------------------------------------------------------
_RE_HASH_NUM = re.compile(r"#\s*([A-Za-z]{0,3}\d{1,4})\b")
_RE_SLASH_NUM = re.compile(r"\b([A-Za-z]{0,3}\d{1,4})\s*/\s*[A-Za-z]{0,3}\d{1,4}\b")
_RE_TRAIL_NUM = re.compile(r"\b([A-Za-z]{0,3}\d{2,4})\b(?=\s*$)")
_RE_PAREN = re.compile(r"\(([^)]*)\)")
_RE_YEAR = re.compile(r"\b(19\d{2}|20\d{2})\b")

# Words that are never part of a card name / set hint.
_NOISE_WORDS = {
    "pokemon", "pokémon", "kort", "korta", "kortene", "card", "cards", "tcg",
    "holo", "reverse", "reverse holo", "foil", "japansk", "japanese", "eng",
    "english", "nm", "lp", "mp", "hp", "dmg", "psa", "gem", "mint",
}
_VARIANT_HINTS = {
    "poke ball pattern", "master ball pattern", "reverse holo", "holo",
    "1st edition", "first edition", "shadowless", "promo",
}


def number_norm(raw: Any) -> str:
    """Normalise a card number for comparison: ``"004"``/``"048/102"`` → ``"4"``.

    Keeps any letter prefix (``TG05`` → ``tg5``, ``SV044`` → ``sv44``) and drops
    leading zeros on the numeric part so ``"004"`` and ``"4"`` compare equal.
    """
    text = str(raw or "").strip().split("/")[0].strip()
    text = re.sub(r"[^0-9A-Za-z]", "", text)
    m = re.match(r"^([A-Za-z]*)(\d+)$", text)
    if m:
        return f"{m.group(1).lower()}{int(m.group(2))}"
    return text.lower()


def _clean_name(text: str) -> str:
    """Reduce heading noise to a bare candidate card name."""
    text = re.sub(r"\([^)]*\)", " ", text)          # drop parentheticals
    text = re.sub(r"#\s*[A-Za-z]{0,3}\d{1,4}", " ", text)   # drop "#101"
    text = re.sub(r"\b[A-Za-z]{0,3}\d{1,4}\s*/\s*[A-Za-z]{0,3}\d{1,4}\b", " ", text)
    text = re.sub(r"[|/,]+", " ", text)
    tokens = [t for t in text.split() if t.strip()]
    kept = [t for t in tokens if t.lower() not in _NOISE_WORDS]
    out = " ".join(kept).strip(" -–—")
    return out


def _split_set_suffix(name: str, index: dict[str, Any] | None) -> tuple[str, str | None]:
    """Peel a trailing known-set phrase off ``name`` using the set index.

    ``"Psychic Energy Base Set"`` → ``("Psychic Energy", "Base Set")`` when
    ``base set`` is a known set. Longest match wins and at least one token must
    remain for the card name; returns ``(name, None)`` when nothing matches so a
    name is never silently mangled.
    """
    if not name or not index:
        return name, None
    by_name = index.get("by_name") or {}
    tokens = name.split()
    for k in range(len(tokens) - 1, 0, -1):
        suffix = " ".join(tokens[-k:])
        if setslib.normalize_name(suffix) in by_name:
            return " ".join(tokens[:-k]).strip(), suffix
    return name, None


def parse_heading(heading: str, index: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extract ``{card_name, card_number, set_hint, year, variant_hint, raw}``."""
    raw = heading or ""
    number = None
    m = _RE_HASH_NUM.search(raw) or _RE_SLASH_NUM.search(raw)
    if not m:
        m = _RE_TRAIL_NUM.search(raw)
    if m:
        number = m.group(1)

    parens = [p.strip() for p in _RE_PAREN.findall(raw) if p.strip()]
    year = None
    ym = _RE_YEAR.search(raw)
    if ym:
        year = int(ym.group(1))

    set_hint = None
    variant_hint = None
    for p in parens:
        low = p.lower()
        if _RE_YEAR.fullmatch(p):
            continue
        if low in _VARIANT_HINTS or any(v in low for v in _VARIANT_HINTS):
            variant_hint = p
        else:
            set_hint = p

    # If the set hint survived as the last token in the name, strip it out.
    name = _clean_name(raw)
    if set_hint:
        name = re.sub(re.escape(set_hint), " ", name, flags=re.I).strip(" -–—")
    if year:
        name = re.sub(rf"\b{year}\b", " ", name).strip(" -–—")
    name = re.sub(r"\s+", " ", name).strip()

    # No parenthetical set? Peel a known set name off the tail of the cleaned
    # name (e.g. "Psychic Energy Base Set" -> set_hint "Base Set", name "Psychic
    # Energy"), which materially sharpens the planned /search queries.
    stripped, suffix = _split_set_suffix(name, index)
    if suffix and not set_hint:
        name, set_hint = stripped, suffix

    return {
        "raw": raw,
        "card_name": name or None,
        "card_number": number,
        "set_hint": set_hint,
        "variant_hint": variant_hint,
        "year": year,
    }


def plan_queries(parsed: dict[str, Any], index: dict[str, Any] | None, limit: int) -> list[str]:
    """Ordered, de-duplicated PokeWallet ``/search`` query strings (most precise first)."""
    queries: list[str] = []
    name = parsed.get("card_name")
    number = parsed.get("card_number")
    set_hint = parsed.get("set_hint")

    if name and number:
        queries.append(f"{name} {number}")
    if set_hint and number:
        queries.append(f"{set_hint} {number}")
    if name:
        queries.append(name)
    if set_hint:
        queries.append(set_hint)

    # Canonical set name (handles Collectr/FINN naming drift) for the +number form.
    if index and set_hint and number:
        entry, _method = setslib.lookup(index, set_hint)
        if entry and entry.get("name"):
            queries.append(f"{entry['name']} {number}")

    deduped = list(dict.fromkeys(q.strip() for q in queries if q and q.strip()))
    return deduped[:limit] if limit > 0 else deduped


# --- candidate scoring ------------------------------------------------------
def _token_overlap(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def _base_name(value: Any) -> str:
    """``"Roaring Moon ex - 090/066"`` → normalised ``"roaring moon ex"``."""
    text = str(value or "").split(" - ", 1)[0]
    text = re.sub(r"\([^)]*\)", " ", text)
    return setslib.normalize_name(text)


def score_candidate(parsed: dict[str, Any], card: dict) -> dict[str, Any]:
    """Score one PokeWallet card against the parsed listing identity.

    Signals (independent): card **number** agrees, **name** agrees (normalised
    equality or strong token overlap), **set** hint agrees, and whether a price
    exists. Returns ``{score, flags, identity, price}`` — a *score*, never a
    silent accept, so a weak match stays visibly weak.
    """
    identity = pricelib.card_identity(card)
    price = pricelib.extract_prices(card)
    info = card.get("card_info") or card

    flags: list[str] = []
    score = 0.0

    num_ok = False
    if parsed.get("card_number"):
        num_ok = number_norm(info.get("card_number")) == number_norm(parsed["card_number"])
        if num_ok:
            score += 40
            flags.append("number")

    name_ok = False
    want = _base_name(parsed.get("card_name"))
    got = _base_name(info.get("name"))
    if want and got:
        if want == got:
            name_ok = True
            score += 40
            flags.append("name_exact")
        elif want in got or got in want:
            name_ok = True
            score += 34
            flags.append("name_substr")
        else:
            ov = _token_overlap(want, got)
            if ov >= 0.6:
                name_ok = True
                score += round(30 * ov)
                flags.append(f"name_tokens{int(ov * 100)}")

    if parsed.get("set_hint"):
        sh = setslib.normalize_name(parsed["set_hint"])
        got_set = setslib.normalize_name(info.get("set_name"))
        got_code = str(info.get("set_code") or "").lower()
        if sh and (sh in got_set or got_set in sh or sh == got_code):
            score += 20
            flags.append("set")

    if price.get("price_source") and price.get("price_source") != "none":
        score += 5
        flags.append("has_price")

    return {
        "score": round(score),
        "flags": flags,
        "num_ok": num_ok,
        "name_ok": name_ok,
        "identity": identity,
        "price": price,
    }


def _native_price(price: dict) -> tuple[float | None, str | None]:
    """Best native price + currency: TCGPlayer (USD) preferred, then CardMarket (EUR)."""
    if price.get("tcg_market") is not None:
        return float(price["tcg_market"]), "USD"
    if price.get("cmk_trend") is not None:
        return float(price["cmk_trend"]), "EUR"
    if price.get("tcg_low") is not None:
        return float(price["tcg_low"]), "USD"
    if price.get("cmk_avg") is not None:
        return float(price["cmk_avg"]), "EUR"
    return None, None


# --- query cache (append-only, newest-wins) ---------------------------------
def load_cache(path: Path = CACHE_JSONL) -> dict[str, dict]:
    """Newest cached entry per normalised query from the append-only JSONL."""
    latest: dict[str, dict] = {}
    if not path.exists():
        return latest
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = str(rec.get("query_key") or "")
            if key:
                latest[key] = rec
    return latest


def cache_age_hours(rec: dict) -> float | None:
    text = str(rec.get("fetched_at") or "")
    if not text:
        return None
    try:
        when = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - when).total_seconds() / 3600.0


def store_cache(query: str, results: list[dict], path: Path = CACHE_JSONL) -> None:
    append_jsonl(path, {
        "query": query,
        "query_key": setslib.normalize_name(query),
        "fetched_at": utc_iso(),
        "count": len(results),
        "results": results,
    })


# --- API --------------------------------------------------------------------
def search_cards(client: PokeWalletClient, query: str) -> list[dict]:
    """One ``/search`` call → list of card dicts (raises on transport failure)."""
    resp = client.search(q=query, limit=20)
    if not resp.ok or not isinstance(resp.data, dict):
        return []
    results = resp.data.get("results")
    return [c for c in results if isinstance(c, dict)] if isinstance(results, list) else []


def resolve_queries(
    client: PokeWalletClient | None,
    queries: list[str],
    cache: dict[str, dict],
    *,
    cache_hours: float,
    offline: bool,
) -> tuple[list[dict], int, bool]:
    """Return ``(cards, calls_spent, cache_hit)`` merging cached + fresh results.

    Cache hit if *any* query was served fresh from cache. Only unique cards are
    returned (by ``id``), preserving order. In ``offline`` mode no API call is
    made and a missing client is tolerated (the cache is still consulted).
    """
    if not offline and client is None:
        offline = True
    cards: list[dict] = []
    seen_ids: set[str] = set()
    calls = 0
    cache_hit = False

    def _merge(items: list[dict]) -> None:
        for c in items:
            cid = str(c.get("id") or "")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                cards.append(c)

    for q in queries:
        key = setslib.normalize_name(q)
        rec = cache.get(key)
        age = cache_age_hours(rec) if rec else None
        if rec and age is not None and age <= cache_hours:
            _merge(list(rec.get("results") or []))
            cache_hit = True
            continue
        if offline:
            continue
        try:
            assert client is not None  # guaranteed: offline paths returned above
            items = search_cards(client, q)
        except (BudgetExhausted, MissingApiKey):
            raise
        calls += 1
        store_cache(q, items)
        cache[key] = {
            "query": q, "query_key": key, "fetched_at": utc_iso(),
            "count": len(items), "results": items,
        }
        _merge(items)
        if items:
            # A precise query that yields hits is enough; don't spend more calls.
            break
    return cards, calls, cache_hit


# --- overlay assembly -------------------------------------------------------
def build_overlay(
    listing: dict[str, Any],
    parsed: dict[str, Any],
    queries: list[str],
    cards: list[dict],
    *,
    calls_spent: int,
    cache_hit: bool,
    fx: dict[str, float],
    max_candidates: int,
) -> dict[str, Any]:
    """Assemble the overlay payload for one listing."""
    scored = [dict(score_candidate(parsed, c), card=c) for c in cards]
    scored.sort(key=lambda s: (-s["score"], s["identity"].get("pk_set_name") or ""))
    top = scored[:max_candidates]

    best = scored[0] if scored and scored[0]["score"] >= 60 and scored[0]["num_ok"] else None

    candidates = []
    for s in top:
        ident = s["identity"]
        nat, cur = _native_price(s["price"])
        candidates.append({
            "pk_id": ident.get("pk_id"),
            "name": ident.get("pk_name"),
            "set_name": ident.get("pk_set_name"),
            "set_code": ident.get("pk_set_code"),
            "set_id": ident.get("pk_set_id"),
            "card_number": ident.get("pk_card_number"),
            "rarity": ident.get("pk_rarity"),
            "tcgplayer_url": ident.get("tcgplayer_url"),
            "price_native": nat,
            "price_currency": cur,
            "price_source": s["price"].get("price_source"),
            "tcg_market": s["price"].get("tcg_market"),
            "cmk_trend": s["price"].get("cmk_trend"),
            "score": s["score"],
            "flags": s["flags"],
        })

    finn_nok = listing.get("finn_price_nok")
    value: dict[str, Any] | None = None
    if best:
        nat, cur = _native_price(best["price"])
        if nat is not None and cur:
            rate = fx.get(cur)
            est_nok = round(nat * rate) if rate else None
            value = {
                "source": best["price"].get("price_source"),
                "native": nat,
                "currency": cur,
                "est_nok": est_nok,
                "fx_rate": rate,
                "estimated": True,
                "finn_nok": finn_nok,
                "delta_nok": (finn_nok - est_nok) if (finn_nok is not None and est_nok is not None) else None,
            }

    name_for_pc = parsed.get("card_name") or listing.get("heading") or ""
    pc_query = urllib.parse.quote_plus(f"{name_for_pc} {parsed.get('card_number') or ''}".strip())
    pricecharting_url = f"https://www.pricecharting.com/search-products?q={pc_query}&type=prices"

    return {
        "parser_version": PARSER_VERSION,
        "generated_at": utc_iso(),
        "finn_kode": listing.get("finn_kode"),
        "url": listing.get("url"),
        "heading": listing.get("heading"),
        "status": listing.get("status"),
        "location": listing.get("location"),
        "finn_price_nok": finn_nok,
        "parsed": {k: parsed.get(k) for k in
                   ("card_name", "card_number", "set_hint", "variant_hint", "year")},
        "queries": queries,
        "calls_spent": calls_spent,
        "cache_hit": cache_hit,
        "candidates": candidates,
        "best": ({
            "pk_id": best["identity"].get("pk_id"),
            "name": best["identity"].get("pk_name"),
            "set_name": best["identity"].get("pk_set_name"),
            "card_number": best["identity"].get("pk_card_number"),
            "score": best["score"],
            "flags": best["flags"],
        } if best else None),
        "value": value,
        "pricecharting_url": pricecharting_url,
        "pricecharting_confirmed": False,
        "notes": [
            "Prices are PokeWallet market values (TCGPlayer USD / CardMarket EUR).",
            "est_nok uses an APPROXIMATE fx rate and is marked estimated=true.",
            "PriceCharting link is stored for reference only; unconfirmed until you confirm.",
        ],
    }


# --- listing normalisers ----------------------------------------------------
def listing_from_search(rec: dict) -> dict[str, Any]:
    return {
        "finn_kode": rec.get("finn_kode"),
        "url": rec.get("canonical_url"),
        "heading": rec.get("heading"),
        "finn_price_nok": rec.get("price_amount"),
        "status": None,
        "location": rec.get("location"),
    }


def listing_from_ad(rec: dict) -> dict[str, Any]:
    return {
        "finn_kode": rec.get("finn_kode"),
        "url": rec.get("url"),
        "heading": rec.get("title"),
        "finn_price_nok": rec.get("price_nok"),
        "status": rec.get("status"),
        "location": rec.get("location_text"),
    }


# --- match one listing ------------------------------------------------------
def match_listing(
    listing: dict[str, Any],
    *,
    client: PokeWalletClient | None,
    index: dict[str, Any] | None,
    cache: dict[str, dict],
    cache_hours: float,
    offline: bool,
    fx: dict[str, float],
    max_queries: int,
    max_candidates: int,
) -> dict[str, Any]:
    parsed = parse_heading(listing.get("heading") or "", index)
    queries = plan_queries(parsed, index, max_queries)
    # NOTE: resolve_queries still consults the cache when offline, so it must be
    # called even with no client. The previous `... if client else ([],0,False)`
    # guard skipped the cache entirely — that was why offline always missed.
    cards, calls, cache_hit = resolve_queries(
        client, queries, cache,
        cache_hours=cache_hours, offline=offline or client is None,
    )
    return build_overlay(
        listing, parsed, queries, cards,
        calls_spent=calls, cache_hit=cache_hit, fx=fx, max_candidates=max_candidates,
    )


# --- CLI --------------------------------------------------------------------
def _load_index() -> dict[str, Any] | None:
    try:
        sets = setslib.load_sets_payload()
    except FileNotFoundError:
        return None
    return setslib.build_index(sets)


def _read_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--heading", help="a single listing heading/title")
    src.add_argument("--from-jsonl", metavar="FILE",
                     help="match every listing in a search run's all_ads.jsonl")
    src.add_argument("--ad-json", metavar="FILE",
                     help="match a single archived ad's parsed JSON (finn_ad.py)")
    parser.add_argument("--finn-price", type=float, default=None,
                        help="asking price in NOK (with --heading)")
    parser.add_argument("--limit", type=int, default=0,
                        help="max listings to process (0 = all)")
    parser.add_argument("--max-calls", type=int, default=25,
                        help="max PokeWallet /search calls this run (0 = unlimited)")
    parser.add_argument("--max-queries", type=int, default=2,
                        help="max query strings per listing (0 = all)")
    parser.add_argument("--max-candidates", type=int, default=5,
                        help="candidates kept in the overlay per listing")
    parser.add_argument("--cache-hours", type=float, default=24.0,
                        help="reuse a cached query within this many hours")
    parser.add_argument("--delay", type=float, default=0.5, help="base delay between calls (s)")
    parser.add_argument("--jitter", type=float, default=0.5, help="random jitter (s)")
    parser.add_argument("--fx-usd", type=float, default=FX_DEFAULTS["USD"], help="NOK per USD")
    parser.add_argument("--fx-eur", type=float, default=FX_DEFAULTS["EUR"], help="NOK per EUR")
    parser.add_argument("--offline", action="store_true",
                        help="parse + plan only; use cache but make no API calls")
    parser.add_argument("--dry-run", action="store_true", help="alias for --offline")
    parser.add_argument("--outdir", default=str(MATCH_DIR), help="output dir for overlays")
    parser.add_argument("--json", action="store_true", help="print overlays as JSON")
    args = parser.parse_args(argv)

    offline = args.offline or args.dry_run
    fx = {"USD": args.fx_usd, "EUR": args.fx_eur}
    outdir = ensure_dir(args.outdir)
    ensure_dir(CACHE_DIR)

    # --- build the listing list ---
    listings: list[dict[str, Any]] = []
    if args.heading:
        listings.append({
            "finn_kode": None, "url": None, "heading": args.heading,
            "finn_price_nok": args.finn_price, "status": None, "location": None,
        })
    elif args.from_jsonl:
        for rec in _read_jsonl(Path(args.from_jsonl)):
            listings.append(listing_from_search(rec))
    else:
        rec = json.loads(Path(args.ad_json).read_text(encoding="utf-8"))
        listings.append(listing_from_ad(rec))

    if args.limit > 0:
        listings = listings[: args.limit]

    index = _load_index()
    cache = load_cache()

    client: PokeWalletClient | None = None
    if not offline:
        client = PokeWalletClient(verbose=True)
        if not client.has_key():
            print(f"ERROR: {pwconfig.API_KEY_ENV} not set; re-run with --offline to plan only.")
            return 2

    print("=" * 88)
    print(f"FINN matcher  |  {len(listings)} listing(s)  |  offline={offline}  "
          f"max_calls={args.max_calls or 'unlimited'}  index={'yes' if index else 'NO'}")
    print("=" * 88)

    overlays: list[dict] = []
    calls = 0
    for i, listing in enumerate(listings, 1):
        if not offline and args.max_calls and calls >= args.max_calls:
            print(f"  reached --max-calls {args.max_calls}; stopping before listing {i}.")
            break
        try:
            ov = match_listing(
                listing, client=client, index=index, cache=cache,
                cache_hours=args.cache_hours, offline=offline, fx=fx,
                max_queries=args.max_queries, max_candidates=args.max_candidates,
            )
        except (BudgetExhausted, MissingApiKey) as exc:
            print(f"  STOP: {exc}")
            break
        calls += ov["calls_spent"]
        overlays.append(ov)
        best = ov.get("best")
        best_txt = (f"{best['name']} [{best['set_name']}] score={best['score']}"
                    if best else "no confident match")
        print(f"  [{i}/{len(listings)}] {ov['heading']!r}")
        print(f"        parsed: name={ov['parsed']['card_name']!r} "
              f"num={ov['parsed']['card_number']!r} set={ov['parsed']['set_hint']!r}")
        print(f"        queries={ov['queries']} calls={ov['calls_spent']} "
              f"cache={ov['cache_hit']} candidates={len(ov['candidates'])}")
        print(f"        best: {best_txt}")
        if ov.get("value"):
            v = ov["value"]
            print(f"        value: FINN {v['finn_nok']} kr vs ~{v['est_nok']} kr "
                  f"({v['native']} {v['currency']}, est) delta={v['delta_nok']}")
        if not offline and i < len(listings):
            time.sleep(args.delay + random.uniform(0, args.jitter))

    # --- write outputs (append-only + timestamped overlay) ---
    for ov in overlays:
        append_jsonl(outdir / "matches.jsonl", ov)
    overlay_path = outdir / f"overlay_{now_ts()}.json"
    overlay_path.write_text(json.dumps(overlays, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")

    print("\n" + "=" * 88)
    print(f"DONE  matched={len(overlays)}/{len(listings)}  api_calls={calls}")
    print(f"  overlay -> {overlay_path}")
    print(f"  cache   -> {CACHE_JSONL}")
    print(f"  matches -> {outdir / 'matches.jsonl'}")
    print("=" * 88)
    if args.json:
        print(json.dumps(overlays, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
