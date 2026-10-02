#!/usr/bin/env python3
"""pokewallet_client.py — one CLI for every PokeWallet API endpoint.

Run with ``uv run pokewallet/pokewallet_client.py <command> [options]``.

Every call saves the raw response to ``data/pokewallet/raw/`` and appends to
``logs/ratelog.csv`` (unless ``--no-save``). The rate budget is respected; use
``--force`` to override the safety floor and ``--dry-run`` to preview the URL.

Examples
--------
    uv run pokewallet/pokewallet_client.py health
    uv run pokewallet/pokewallet_client.py search -q "pikachu" --limit 5 --top 5
    uv run pokewallet/pokewallet_client.py search --param "set_id=23520" --param "q=004"
    uv run pokewallet/pokewallet_client.py card pk_4c87dcac... --json
    uv run pokewallet/pokewallet_client.py sets --top 10
    uv run pokewallet/pokewallet_client.py prices base1      # PRO: expect blocked
"""

from __future__ import annotations

import argparse
import json
import sys

from pwlib import config
from pwlib.api import ApiResponse, BudgetExhausted, MissingApiKey, PokeWalletClient
from pwlib.util import write_json


# ---------------------------------------------------------------------------
# summary rendering
# ---------------------------------------------------------------------------
def _n(value: object) -> str:
    """Render a possibly-None value compactly."""
    return "—" if value is None else str(value)


def _price_of(result: dict) -> str:
    tcg = result.get("tcgplayer") or {}
    for price in tcg.get("prices", []) or []:
        if price.get("market_price") is not None:
            return f"${price['market_price']:.2f} (tcg/{price.get('sub_type_name') or '?'})"
    cm = result.get("cardmarket") or {}
    if cm.get("trend") is not None:
        return f"€{cm['trend']:.2f} (cmk/trend)"
    if cm.get("avg") is not None:
        return f"€{cm['avg']:.2f} (cmk/avg)"
    return "no price"


def _render_search(data: dict, top: int) -> None:
    pag = data.get("pagination", {}) or {}
    meta = data.get("metadata", {}) or {}
    print(f"query={_n(data.get('query'))!r} total={_n(pag.get('total'))} "
          f"page={_n(pag.get('page'))}/{_n(pag.get('total_pages'))}")
    if meta:
        print("  sources:", ", ".join(f"{k}={v}" for k, v in meta.items()))
    results = data.get("results", []) or []
    for i, r in enumerate(results[:top], 1):
        info = r.get("card_info", {}) or {}
        print(f"  {i:>2}. {_n(info.get('name'))}  [{_n(info.get('set_code'))} "
              f"{_n(info.get('card_number'))}]  id={_n(r.get('id'))[:18]}…  {_price_of(r)}")
    if len(results) > top:
        print(f"  … {len(results) - top} more (use --json for everything)")


def _render_card(data: dict) -> None:
    info = data.get("card_info", {}) or {}
    print(f"{_n(info.get('name'))}  [{_n(info.get('set_name'))} / {_n(info.get('set_code'))} "
          f"{_n(info.get('card_number'))}]")
    print(f"  id={_n(data.get('id'))}  rarity={_n(info.get('rarity'))} "
          f"type={_n(info.get('product_type'))}  images={_n((data.get('images') or {}).get('languages'))}")
    print(f"  {_price_of(data)}")


def _render_sets(data: dict | list, top: int) -> None:
    sets = data.get("sets", data.get("data", [])) if isinstance(data, dict) else data
    if not isinstance(sets, list):
        print("  (unrecognised sets payload; use --json)")
        return
    print(f"sets: {len(sets)}")
    for s in sets[:top]:
        if isinstance(s, dict):
            print(f"  {_n(s.get('set_code')):<10} {_n(s.get('set_id')):<8} {_n(s.get('name'))}")


def _render_generic(data: object) -> None:
    if isinstance(data, dict):
        print("keys:", ", ".join(data.keys()))
        for key in ("error", "message", "detail"):
            if key in data:
                print(f"  {key}: {data[key]}")
    else:
        print("payload type:", type(data).__name__)


def render_summary(resp: ApiResponse, top: int) -> None:
    # The per-call summary line is already printed by the client's request
    # logger when verbose; render only the body here to avoid a duplicate.
    data = resp.data
    if data is None:
        print(f"  (non-JSON body, {len(resp.text)} chars)")
        return
    if resp.endpoint == "search" and isinstance(data, dict) and "results" in data:
        _render_search(data, top)
    elif resp.endpoint == "card" and isinstance(data, dict):
        _render_card(data)
    elif resp.endpoint in ("sets",) or (resp.endpoint == "set" and isinstance(data, dict)):
        _render_sets(data, top)
    elif resp.api_error:
        print(f"  api_error: {resp.api_error}")
    else:
        _render_generic(data)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true",
                        help="print the raw JSON body to stdout")
    common.add_argument("--out", metavar="FILE",
                        help="also write the parsed JSON to FILE (never overwrites)")
    common.add_argument("--no-save", action="store_true",
                        help="do not persist the raw response under data/")
    common.add_argument("--dry-run", action="store_true",
                        help="show the URL without sending a request")
    common.add_argument("--force", action="store_true",
                        help="ignore the rate-budget safety floor")
    common.add_argument("--min-hour", type=int, default=None,
                        help=f"hourly floor before refusing (default {config.MIN_HOUR_REMAINING_DEFAULT})")
    common.add_argument("--min-day", type=int, default=None,
                        help=f"daily floor before refusing (default {config.MIN_DAY_REMAINING_DEFAULT})")
    common.add_argument("--quiet", action="store_true",
                        help="only print the final payload/summary, not per-call chatter")

    parser = argparse.ArgumentParser(
        prog="pokewallet_client.py",
        description="Generic CLI for the PokeWallet API (raw-saving, rate-aware).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", parents=[common], help="GET /health")
    sub.add_parser("root", parents=[common], help="GET /")

    p = sub.add_parser("search", parents=[common], help="GET /search")
    p.add_argument("-q", "--query", default=None)
    p.add_argument("--page", type=int, default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--param", action="append", default=[], metavar="k=v",
                   help="extra query parameters (repeatable)")
    p.add_argument("--top", type=int, default=10,
                   help="rows to show in the human summary")

    p = sub.add_parser("card", parents=[common], help="GET /cards/:id")
    p.add_argument("card_id")

    p = sub.add_parser("sets", parents=[common], help="GET /sets")
    p.add_argument("--top", type=int, default=10)

    p = sub.add_parser("set", parents=[common], help="GET /sets/:setCode")
    p.add_argument("set_code")
    p.add_argument("--page", type=int, default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--top", type=int, default=10)

    p = sub.add_parser("images", parents=[common], help="GET /images/:id")
    p.add_argument("card_id")

    # PRO endpoints — kept so we notice the day they unlock.
    p = sub.add_parser("prices", parents=[common], help="GET /prices/:setCode [PRO]")
    p.add_argument("set_code")
    p = sub.add_parser("price-history", parents=[common], help="GET /cards/:id/price-history [PRO]")
    p.add_argument("card_id")
    p = sub.add_parser("statistics", parents=[common], help="GET /sets/:setCode/statistics [PRO]")
    p.add_argument("set_code")
    sub.add_parser("trending", parents=[common], help="GET /sets/trending [PRO]")
    p = sub.add_parser("completion-value", parents=[common], help="GET /sets/:setCode/completion-value [PRO]")
    p.add_argument("set_code")
    sub.add_parser("top-cards", parents=[common], help="GET /analytics/top-cards [PRO]")

    return parser


def _parse_extras(pairs: list[str]) -> dict:
    extra: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--param must be k=v, got: {pair!r}")
        key, value = pair.split("=", 1)
        extra[key] = value
    return extra


def dispatch(client: PokeWalletClient, args: argparse.Namespace) -> ApiResponse:
    common = dict(
        save=not args.no_save,
        dry_run=args.dry_run,
        force=args.force,
        min_hour=args.min_hour,
        min_day=args.min_day,
    )
    cmd = args.command
    if cmd == "health":
        return client.health(**common)
    if cmd == "root":
        return client.root(**common)
    if cmd == "search":
        return client.search(q=args.query, page=args.page, limit=args.limit,
                             extra=_parse_extras(args.param), **common)
    if cmd == "card":
        return client.card(args.card_id, **common)
    if cmd == "sets":
        return client.sets(**common)
    if cmd == "set":
        return client.set(args.set_code, page=args.page, limit=args.limit, **common)
    if cmd == "images":
        return client.images(args.card_id, **common)
    if cmd == "prices":
        return client.prices(args.set_code, **common)
    if cmd == "price-history":
        return client.price_history(args.card_id, **common)
    if cmd == "statistics":
        return client.statistics(args.set_code, **common)
    if cmd == "trending":
        return client.trending(**common)
    if cmd == "completion-value":
        return client.completion_value(args.set_code, **common)
    if cmd == "top-cards":
        return client.top_cards(**common)
    raise SystemExit(f"unknown command: {cmd}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = PokeWalletClient(
        save=not args.no_save,
        verbose=not args.quiet,
        min_hour=args.min_hour,
        min_day=args.min_day,
    )
    if not client.has_key():
        print(f"warning: {config.API_KEY_ENV} is not set — authenticated calls will fail.",
              file=sys.stderr)

    try:
        resp = dispatch(client, args)
    except BudgetExhausted as exc:
        print(f"budget guard: {exc}", file=sys.stderr)
        return 2
    except MissingApiKey as exc:
        print(f"missing key: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"dry-run URL: {resp.url}")
        return 0

    if args.out and resp.data is not None:
        path = write_json(args.out, resp.data)
        print(f"wrote: {path}")

    if args.json:
        if resp.data is not None:
            print(json.dumps(resp.data, indent=2, ensure_ascii=False))
        else:
            print(resp.text)
    elif not args.quiet:
        render_summary(resp, getattr(args, "top", 10))
    else:
        print(resp.summary_line())

    if not resp.ok:
        print(f"request failed (HTTP {resp.status})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
