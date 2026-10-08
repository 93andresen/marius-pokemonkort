#!/usr/bin/env python3
"""finn_price.py — price a FINN ad *and every card it enumerates* via PokeWallet.

The existing ``finn_matcher.py`` prices **one heading -> one card**.  Many FINN
ads instead sell a *list* ("Liste over kort: ...") of dozens of cards.  This
module adds the missing per-ad / per-card pricing layer **on top of the same
cached, budget-capped query engine** — it never opens a second, unbudgeted path
to the API.

For an ad it produces:

* a **listing-level** value (from the ad title, via ``finn_matcher``), and
* a **per-card** value for every row ``finn_cards`` extracted from the
  description (using the ad's ``finn_identify`` set matches to sharpen queries),
* a ``deal`` block comparing the PokeWallet market value (NOK, ``estimated=true``)
  against the seller's asking price: ``ratio = market / asking`` (higher = better
  deal) and ``delta_nok = asking - market`` (negative = a deal).

Honesty rules (``SCRAPING_PROMPT.md`` §6): a name-only hit is *low* confidence and
left **unpriced** unless you explicitly pass ``--price-low`` (the Mew/Mewtwo
trap); coverage is reported explicitly so a partial sum is never passed off as a
complete one; nothing is overwritten (append-only ``pricing.jsonl`` + a
timestamped ``pricing_<ts>.json``).

CLI
---
  # Price one archived ad, offline (cache only, 0 API calls):
  uv run finn/finn_price.py --ad-json data/finn/annonser/<slug>/<kode>.json --offline --json

  # One heading (as if it were a listing), offline:
  uv run finn/finn_price.py --heading "Psychic Energy #101 Base Set (1999)" --finn-price 9 --offline

  # Price a whole run's listings (live unless --offline):
  uv run finn/finn_price.py --from-jsonl data/finn/searches/<run>/all_ads.jsonl --max-calls 25
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

# --- path setup: reuse finn/ siblings and pwlib (repo/pokewallet) -----------
_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent))                      # finn/  -> finnlib
sys.path.insert(0, str(_HERE.parents[1] / "pokewallet"))   # -> pwlib

import finn_cards as fc  # noqa: E402  (local sibling module)
import finn_identify as fi  # noqa: E402
import finn_matcher as fm  # noqa: E402
import finnlib as fl  # noqa: E402
from pwlib import sets as setslib  # noqa: E402
from pwlib.api import BudgetExhausted, MissingApiKey, PokeWalletClient  # noqa: E402
from pwlib.util import append_jsonl, ensure_dir, now_ts, utc_iso  # noqa: E402

PRICE_VERSION = "finn_price/1.0.0"

PRICE_DIR: Path = fm.MATCH_DIR
PRICE_JSONL: Path = PRICE_DIR / "pricing.jsonl"

# Confidence levels that are good enough to price by default.  "low" is only
# priced when the caller opts in (--price-low); "none" is never priced.
PRICEABLE = ("high", "medium")


def log(message: str) -> None:
    """Human-facing progress goes to stderr so ``--json`` stdout stays parseable.

    Nothing is hidden: stderr is shown in the terminal alongside stdout.
    """
    print(message, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- #
# Confidence + deal math
# --------------------------------------------------------------------------- #


def confidence_of(scored: dict[str, Any] | None, *, set_expected: bool = False) -> str:
    """Rate a scored candidate: ``high`` / ``medium`` / ``low`` / ``none``.

    Conservative and loud (mirrors ``finn_matcher``'s "never trust a hit blindly"):

    * no name agreement at all -> ``none``;
    * name **and** card number agree -> ``high``;
    * name agrees and the *requested* set matched -> ``medium``;
    * name agrees, a set was expected but is **not** matched -> ``low`` (red flag);
    * exact name, no set was requested -> ``medium`` (nothing to contradict it);
    * weak/partial name only -> ``low``.
    """
    if not scored or not scored.get("name_ok"):
        return "none"
    if scored.get("num_ok"):
        return "high"
    flags = scored.get("flags") or []
    if "set" in flags:
        return "medium"
    if set_expected:
        return "low"
    if "name_exact" in flags:
        return "medium"
    return "low"


def deal_math(market_value_nok: float | None,
              asking_price_nok: float | None) -> dict[str, Any]:
    """``ratio = market / asking`` (higher = better); ``delta_nok = asking - market``.

    ``ratio``/``delta_nok`` are ``None`` when either side is missing, and the
    ratio is ``None`` for a zero asking price (never divide by zero).
    """
    delta: int | float | None = None
    ratio: float | None = None
    if market_value_nok is not None and asking_price_nok is not None:
        delta = round(asking_price_nok - market_value_nok)
        if asking_price_nok:
            ratio = round(market_value_nok / asking_price_nok, 4)
    return {
        "market_value_nok": market_value_nok,
        "asking_price_nok": asking_price_nok,
        "delta_nok": delta,
        "ratio": ratio,
    }


# --------------------------------------------------------------------------- #
# Per-card pricing
# --------------------------------------------------------------------------- #


def _matching_set_hint(set_name: Any, set_hints: list[str]) -> str | None:
    """The ad set hint that best matches a candidate card's set (or ``None``)."""
    if not set_name or not set_hints:
        return None
    got = setslib.normalize_name(set_name)
    for hint in set_hints:
        want = setslib.normalize_name(hint)
        if want and (want in got or got in want):
            return hint
    return None


def _card_queries(name: str, set_hints: list[str], limit: int) -> list[str]:
    """Ordered queries for one enumerated card (set-qualified first, then bare).

    The bare name is always kept reachable within the first two queries so a
    card list never becomes entirely unpricable just because the ad named sets.
    """
    queries: list[str] = []
    if set_hints:
        queries.append(f"{name} {set_hints[0]}")
    queries.append(name)
    for hint in set_hints[1:]:
        queries.append(f"{name} {hint}")
    deduped = list(dict.fromkeys(q.strip() for q in queries if q and q.strip()))
    return deduped[:limit] if limit > 0 else deduped


def _price_card(
    card: dict[str, Any],
    *,
    client: PokeWalletClient | None,
    cache: dict[str, dict],
    cache_hours: float,
    offline: bool,
    fx: dict[str, float],
    set_hints: list[str],
    max_queries: int,
    price_low: bool,
) -> tuple[dict[str, Any], int, bool]:
    """Price a single enumerated card. Returns ``(row, calls_spent, cache_hit)``."""
    name = card["name"]
    queries = _card_queries(name, set_hints, max_queries)
    found, calls, cache_hit = fm.resolve_queries(
        client, queries, cache, cache_hours=cache_hours, offline=offline,
    )

    scored: list[dict[str, Any]] = []
    for cand in found:
        info = cand.get("card_info") or cand
        hint = _matching_set_hint(info.get("set_name"), set_hints)
        parsed = {"card_name": name, "card_number": None, "set_hint": hint}
        s = dict(fm.score_candidate(parsed, cand), card=cand)
        scored.append(s)
    scored.sort(key=lambda s: -s["score"])
    top = scored[0] if scored else None

    conf = confidence_of(top, set_expected=bool(set_hints))
    nat, cur = fm._native_price(top["price"]) if top else (None, None)
    priceable = nat is not None and cur is not None
    may_price = conf in PRICEABLE or (price_low and conf == "low")

    unit: int | None = None
    market: int | None = None
    if may_price and priceable and nat is not None and cur is not None:
        unit = round(nat * fx[cur])
        market = unit * int(card["count"])

    ident = top["identity"] if top else {}
    row: dict[str, Any] = {
        "name": name,
        "count": card["count"],
        "variants": card["variants"],
        "line_index": card["line_index"],
        "query": queries[0] if queries else None,
        "queries": queries,
        "pk_id": ident.get("pk_id"),
        "pk_name": ident.get("pk_name"),
        "pk_set_name": ident.get("pk_set_name"),
        "pk_card_number": ident.get("pk_card_number"),
        "score": top["score"] if top else None,
        "confidence": conf,
        "flags": list(top["flags"]) if top else [],
        "price_native": nat,
        "price_currency": cur,
        "price_source": (top["price"].get("price_source") if top else None),
        "unit_market_value_nok": unit,
        "market_value_nok": market,
        "priced": market is not None,
    }
    if conf in PRICEABLE and not priceable:
        row["flags"].append("no_price_source")
    return row, calls, cache_hit


# --------------------------------------------------------------------------- #
# Listing-level value (reuse the matcher, do not duplicate it)
# --------------------------------------------------------------------------- #


def _listing_confidence(overlay: dict[str, Any]) -> str:
    """Confidence for the listing-level (title-derived) match."""
    if overlay.get("best"):
        return "high"
    flags: set[str] = set()
    for cand in overlay.get("candidates") or []:
        flags.update(cand.get("flags") or [])
    if flags & {"name_exact", "name_substr"} or any(f.startswith("name_tokens") for f in flags):
        return "medium" if "set" in flags else "low"
    return "none"


# --------------------------------------------------------------------------- #
# The main entry point
# --------------------------------------------------------------------------- #


def price_ad(
    record: dict[str, Any],
    *,
    client: PokeWalletClient | None = None,
    index: dict[str, Any] | None = None,
    cache: dict[str, dict] | None = None,
    cache_hours: float = 24.0,
    offline: bool = True,
    fx: dict[str, float] | None = None,
    max_queries: int = 2,
    max_cards: int = 0,
    max_calls: int = 25,
    price_low: bool = False,
) -> dict[str, Any]:
    """Attach a pricing block (listing + per-card + deal) to one parsed ad."""
    cache = cache if cache is not None else {}
    fx = dict(fx or fm.FX_DEFAULTS)
    offline = offline or client is None

    listing = fm.listing_from_ad(record)
    asking = listing.get("finn_price_nok")
    ident = fi.identify_ad(record)
    set_hints = list(ident.get("matched_set_names") or [])

    flags: list[str] = []
    calls = 0
    cache_hit = False

    # --- listing-level (title -> one card), cache-first ---------------------
    overlay = fm.match_listing(
        listing, client=client, index=index, cache=cache,
        cache_hours=cache_hours, offline=offline, fx=fx,
        max_queries=max_queries, max_candidates=5,
    )
    calls += overlay.get("calls_spent", 0)
    cache_hit = cache_hit or bool(overlay.get("cache_hit"))
    listing_conf = _listing_confidence(overlay)
    listing_value = (overlay.get("value") or {}).get("est_nok")

    # --- per-card (description card list) -----------------------------------
    struct = fc.structure(record)
    all_cards = struct["cards"]
    total = len(all_cards)
    considered = all_cards[:max_cards] if max_cards > 0 else all_cards
    if max_cards > 0 and total > max_cards:
        flags.append(f"priced only first {max_cards} of {total} enumerated cards")

    rows: list[dict[str, Any]] = []
    for card in considered:
        if not offline and max_calls and calls >= max_calls:
            flags.append(f"reached --max-calls {max_calls}; remaining cards unpriced")
            break
        row, card_calls, card_hit = _price_card(
            card, client=client, cache=cache, cache_hours=cache_hours,
            offline=offline, fx=fx, set_hints=set_hints,
            max_queries=max_queries, price_low=price_low,
        )
        calls += card_calls
        cache_hit = cache_hit or card_hit
        rows.append(row)

    priced_rows = [r for r in rows if r["priced"]]
    priced = len(priced_rows)

    # --- the deal: prefer the (per-card) sum, else the listing value --------
    if priced_rows:
        market_value: int | None = sum(r["market_value_nok"] for r in priced_rows)
        basis = "card_list_sum"
    elif listing_value is not None:
        market_value = listing_value
        basis = "listing_best"
    else:
        market_value = None
        basis = "none"

    deal = deal_math(market_value, asking)
    deal["basis"] = basis

    partial = total > 0 and priced < total
    if total and not struct["card_list_present"]:
        flags.append("no card list found in description")
    if partial:
        flags.append(f"card list only partially priced ({priced}/{total})")
    if asking is None:
        flags.append("no asking price on the ad")

    return {
        "price_version": PRICE_VERSION,
        "generated_at": utc_iso(),
        "finn_kode": listing.get("finn_kode"),
        "url": listing.get("url"),
        "heading": listing.get("heading"),
        "finn_price_nok": asking,
        "identify": {
            "intent_rank": ident.get("intent_rank"),
            "intent": ident.get("intent"),
            "matched_set_names": set_hints,
            "matched_card_names": ident.get("matched_card_names"),
        },
        "set_hints": set_hints,
        "listing": overlay,
        "listing_confidence": listing_conf,
        "listing_value_nok": listing_value,
        "cards": rows,
        "card_coverage": {
            "total": total,
            "considered": len(considered),
            "priced": priced,
            "unpriced": total - priced,
        },
        "partial_card_coverage": partial,
        "deal": deal,
        "calls_spent": calls,
        "cache_hit": cache_hit,
        "flags": flags + list(struct["flags"]),
        "notes": [
            "Market values are PokeWallet values (TCGPlayer USD / CardMarket EUR).",
            "NOK figures use an APPROXIMATE fx rate and are marked estimated.",
            "ratio = market / asking (higher = better deal); delta_nok = asking - market.",
        ],
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--heading", help="a single listing heading/title")
    src.add_argument("--ad-json", metavar="FILE",
                     help="price a single archived ad's parsed JSON (finn_ad.py)")
    src.add_argument("--from-jsonl", metavar="FILE",
                     help="price every listing in a JSONL file (search all_ads.jsonl)")
    parser.add_argument("--finn-price", type=float, default=None,
                        help="asking price in NOK (with --heading)")
    parser.add_argument("--offline", action="store_true",
                        help="use the cache but make no API calls")
    parser.add_argument("--dry-run", action="store_true", help="alias for --offline")
    parser.add_argument("--cache-file", default=str(fm.CACHE_JSONL),
                        help="append-only query cache to read")
    parser.add_argument("--cache-hours", type=float, default=24.0,
                        help="reuse a cached query within this many hours")
    parser.add_argument("--max-cards", type=int, default=0,
                        help="max enumerated cards to price per ad (0 = all)")
    parser.add_argument("--max-queries", type=int, default=2,
                        help="max query strings per card (0 = all)")
    parser.add_argument("--max-calls", type=int, default=25,
                        help="max PokeWallet calls this run (0 = unlimited)")
    parser.add_argument("--price-low", action="store_true",
                        help="also price low-confidence (name-only) candidates")
    parser.add_argument("--fx-usd", type=float, default=fm.FX_DEFAULTS["USD"], help="NOK per USD")
    parser.add_argument("--fx-eur", type=float, default=fm.FX_DEFAULTS["EUR"], help="NOK per EUR")
    parser.add_argument("--delay", type=float, default=0.5, help="base delay between calls (s)")
    parser.add_argument("--jitter", type=float, default=0.5, help="random jitter (s)")
    parser.add_argument("--outdir", default=str(PRICE_DIR), help="output dir for pricing files")
    parser.add_argument("--json", action="store_true", help="print results as JSON on stdout")
    args = parser.parse_args(argv)

    offline = args.offline or args.dry_run
    fx = {"USD": args.fx_usd, "EUR": args.fx_eur}
    outdir = ensure_dir(args.outdir)
    ensure_dir(fm.CACHE_DIR)

    records: list[dict[str, Any]] = []
    if args.heading:
        records.append({"finn_kode": None, "url": None, "title": args.heading,
                        "price_nok": args.finn_price, "status": None,
                        "description_raw": ""})
    elif args.ad_json:
        records.append(json.loads(Path(args.ad_json).read_text(encoding="utf-8")))
    else:
        records.extend(_read_jsonl(Path(args.from_jsonl)))

    index = fm._load_index()
    cache = fm.load_cache(Path(args.cache_file))

    client: PokeWalletClient | None = None
    if not offline:
        client = PokeWalletClient(verbose=True)
        if not client.has_key():
            log("ERROR: API_KEY_POKEWALLET not set; re-run with --offline.")
            return 2

    log("=" * 88)
    log(f"FINN price  |  {len(records)} record(s)  |  offline={offline}  "
        f"max_calls={args.max_calls or 'unlimited'}  index={'yes' if index else 'NO'}")
    log("=" * 88)

    results: list[dict[str, Any]] = []
    calls = 0
    for i, rec in enumerate(records, 1):
        if not offline and args.max_calls and calls >= args.max_calls:
            log(f"  reached --max-calls {args.max_calls}; stopping before record {i}.")
            break
        try:
            res = price_ad(
                rec, client=client, index=index, cache=cache,
                cache_hours=args.cache_hours, offline=offline, fx=fx,
                max_queries=args.max_queries, max_cards=args.max_cards,
                max_calls=args.max_calls, price_low=args.price_low,
            )
        except (BudgetExhausted, MissingApiKey) as exc:
            log(f"  STOP: {exc}")
            break
        calls += res["calls_spent"]
        results.append(res)
        deal = res["deal"]
        log(f"  [{i}/{len(records)}] {res['heading']!r}")
        log(f"        cards: {res['card_coverage']['priced']}/{res['card_coverage']['total']} "
            f"priced  partial={res['partial_card_coverage']}")
        log(f"        deal: basis={deal['basis']} asking={deal['asking_price_nok']} "
            f"market={deal['market_value_nok']} ratio={deal['ratio']} delta={deal['delta_nok']}")
        log(f"        calls={res['calls_spent']} cache={res['cache_hit']}")
        if not offline and i < len(records):
            time.sleep(args.delay + random.uniform(0, args.jitter))

    # --- write outputs (append-only + timestamped snapshot) -----------------
    for res in results:
        append_jsonl(outdir / "pricing.jsonl", res)
    snap = outdir / f"pricing_{now_ts()}.json"
    snap.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    log("=" * 88)
    log(f"DONE  priced={len(results)}/{len(records)}  api_calls={calls}")
    log(f"  pricing  -> {outdir / 'pricing.jsonl'}")
    log(f"  snapshot -> {snap}")
    log("=" * 88)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
