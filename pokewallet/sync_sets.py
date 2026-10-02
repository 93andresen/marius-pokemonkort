#!/usr/bin/env python3
"""sync_sets.py — fetch/normalise the PokeWallet set index.

By default this calls ``GET /sets`` (one request) and writes:
  - ``data/pokewallet/sets/set_index_<ts>.json``  (normalised lookup index)
  - ``data/pokewallet/sets/sets_<ts>.csv``         (human-readable list)
Use ``--cached`` to reuse the newest cached ``/sets`` capture instead of
spending a request.

    uv run pokewallet/sync_sets.py            # fetch fresh
    uv run pokewallet/sync_sets.py --cached   # reuse newest raw capture
"""

from __future__ import annotations

import argparse
import csv
import sys

from pwlib import config, sets as setslib
from pwlib.api import BudgetExhausted, MissingApiKey, PokeWalletClient
from pwlib.util import now_ts, write_json, write_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cached", action="store_true",
                        help="use the newest cached /sets capture (no request)")
    parser.add_argument("--force", action="store_true",
                        help="ignore the rate-budget safety floor")
    args = parser.parse_args(argv)

    if args.cached:
        src = setslib.latest_raw_sets()
        if src is None:
            print("no cached /sets capture; run without --cached first", file=sys.stderr)
            return 2
        print(f"using cached capture: {src}")
        items = setslib.load_sets_payload(src)
    else:
        client = PokeWalletClient()
        try:
            resp = client.sets(force=args.force)
        except BudgetExhausted as exc:
            print(f"budget guard: {exc}", file=sys.stderr)
            return 2
        except MissingApiKey as exc:
            print(f"missing key: {exc}", file=sys.stderr)
            return 2
        if not resp.ok:
            print(f"GET /sets failed: HTTP {resp.status}", file=sys.stderr)
            return 1
        items = setslib.load_sets_payload(resp.saved_json)

    if not items:
        print("no sets returned", file=sys.stderr)
        return 1

    index = setslib.build_index(items)
    ts = now_ts()

    index_path = write_json(
        config.SETS_DIR / f"set_index_{ts}.json",
        {"generated_at": ts, "count": len(items), "index": index},
    )

    # Human-readable CSV, sorted by name.
    rows = sorted(items, key=lambda s: (s.get("name") or "").lower())
    csv_lines = ["name,set_code,set_id,language,card_count,number_count,release_date"]
    for s in rows:
        def esc(v: object) -> str:
            return '"' + str(v if v is not None else "").replace('"', '""') + '"'
        csv_lines.append(",".join([
            esc(s.get("name")), esc(s.get("set_code")), esc(s.get("set_id")),
            esc(s.get("language")), esc(s.get("card_count")),
            esc(s.get("number_count")), esc(s.get("release_date")),
        ]))
    csv_path = write_text(config.SETS_DIR / f"sets_{ts}.csv", "\n".join(csv_lines) + "\n")

    langs: dict[str, int] = {}
    for s in items:
        key = str(s.get("language") or "unknown")
        langs[key] = langs.get(key, 0) + 1

    print(f"sets indexed: {len(items)} (unique names {len(index['by_name'])})")
    print(f"languages: {', '.join(f'{k}={v}' for k, v in sorted(langs.items()))}")
    print(f"index: {index_path}")
    print(f"csv:   {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
