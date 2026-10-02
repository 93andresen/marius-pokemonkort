#!/usr/bin/env python3
"""fetch_loop.py — run :mod:`fetch_prices` repeatedly until the portfolio is done.

The free PokeWallet plan allows only **100 calls/hour**, so a 175-card portfolio
cannot be filled in a single pass. This orchestrator runs a fetch pass, and
whenever the pass stopped early because it hit the hourly budget floor it waits
and tries again — continuing across hourly windows until every card the API
knows about has a price.

It is safe to stop at any time (Ctrl-C): snapshots are append-only and
``fetch_prices`` is resumable, so the next run continues where this one stopped.

    uv run pokewallet/fetch_loop.py                 # fill to completion, <= 12h
    uv run pokewallet/fetch_loop.py --sleep 900     # shorter waits between passes
    uv run pokewallet/fetch_loop.py --max-hours 1   # a bounded background run
    uv run pokewallet/fetch_loop.py --max-passes 1 --sleep 0   # single pass, no wait
"""
from __future__ import annotations

import argparse
import sys
import time

import fetch_prices
from pwlib import config, portfolio, sets as setslib


def portfolio_keys() -> set[tuple[str, str]]:
    """The ``(set_id, number_norm)`` keys the whole portfolio resolves to."""
    index = fetch_prices.load_index()
    _, rows = portfolio.read_rows(str(config.COLLECTR_CSV))
    keys: set[tuple[str, str]] = set()
    for row in rows:
        entry, _ = setslib.lookup(index, (row.get(portfolio.SET_COL) or "").strip())
        number_norm = portfolio.number_norm(row.get(portfolio.NUMBER_COL))
        set_id = (entry or {}).get("set_id")
        if entry and set_id and number_norm:
            keys.add((str(set_id), number_norm))
    return keys


def progress(keys: set[tuple[str, str]]) -> tuple[int, int]:
    """``(cards_with_a_price, total_cards)`` from the append-only JSONL."""
    latest = fetch_prices.load_latest_snapshots(fetch_prices.SNAPSHOT_JSONL)
    done = sum(1 for k in keys if (latest.get(k) or {}).get("found"))
    return done, len(keys)


def _hms(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m{seconds % 60:02d}s"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh-hours", type=float, default=20.0,
                        help="passed through to fetch_prices (default 20)")
    parser.add_argument("--sleep", type=int, default=1800,
                        help="seconds to wait between passes when budget-limited "
                             "(0 = no wait, for testing; default 1800)")
    parser.add_argument("--max-hours", type=float, default=12.0,
                        help="give up after this many hours (default 12)")
    parser.add_argument("--max-passes", type=int, default=0,
                        help="stop after N passes (0 = unlimited)")
    parser.add_argument("--stale-limit", type=int, default=3,
                        help="stop after N consecutive full passes with no new "
                             "matches (cards absent from the API; default 3)")
    args = parser.parse_args(argv)

    keys = portfolio_keys()
    done, total = progress(keys)
    print(f"[loop] portfolio: {done}/{total} cards have a price")
    print(f"[loop] will keep running passes until complete (sleep={args.sleep}s, "
          f"max_hours={args.max_hours:g}, stale_limit={args.stale_limit})")

    started = time.time()
    passes = 0
    stale = 0

    while True:
        passes += 1
        print(f"\n[loop] ===== pass {passes} (elapsed {_hms(time.time() - started)}) =====")
        stats: dict = {}
        rc = fetch_prices.main(["--fresh-hours", str(args.fresh_hours)], stats=stats)
        if rc != 0:
            print(f"[loop] fetch pass returned {rc}; stopping.", file=sys.stderr)
            return rc

        done, total = progress(keys)
        fetched = stats.get("fetched", 0)
        stopped = stats.get("stopped", False)
        print(f"[loop] progress: {done}/{total} cards priced "
              f"(this pass fetched {fetched}, {stats.get('calls', 0)} API calls, "
              f"stopped_early={stopped})")

        if done >= total:
            print(f"[loop] COMPLETE — all {total} portfolio cards have a price.")
            return 0

        if fetched > 0:
            stale = 0
        elif not stopped:
            # A full pass with budget available still found nothing new.
            stale += 1
            print(f"[loop] no new matches in a full pass ({stale}/{args.stale_limit})")
        else:
            print("[loop] budget-limited before any match; will wait and retry "
                  "(not counted as stale)")

        if stale >= args.stale_limit:
            print(f"[loop] stopping: {args.stale_limit} full passes found nothing new; "
                  f"the remaining {total - done} cards are likely absent from the API.")
            return 0

        if args.max_passes and passes >= args.max_passes:
            print(f"[loop] reached --max-passes {args.max_passes}; stopping.")
            return 0

        if (time.time() - started) / 3600.0 >= args.max_hours:
            print(f"[loop] reached --max-hours {args.max_hours:g}; stopping "
                  f"(re-run to continue where this left off).")
            return 0

        if args.sleep <= 0:
            continue
        print(f"[loop] sleeping {args.sleep}s before the next pass "
              f"(Ctrl-C is safe; snapshots are append-only)…")
        time.sleep(args.sleep)


if __name__ == "__main__":
    raise SystemExit(main())
