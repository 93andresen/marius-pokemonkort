#!/usr/bin/env python3
"""Append-only log of every FINN ad you view, plus a query CLI.

The browser tool posts each viewed ad here (see ``tools/local_agent.py``), and you
can then ask questions like *"all the Pichu's I looked at in the last 4 weeks"*:

    uv run tools/history_logger.py --since-days 28 --match pichu

Design rules (repo-wide): append-only — never rewrite or delete; every line is
flushed immediately so a crash loses nothing. Times are ISO-8601 UTC
(``viewed_at``) with a filename-safe local echo (``viewed_ts``).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[1] / "finn"))  # repo finn/ -> finnlib
import finnlib as fl  # noqa: E402

HISTORY_DIR: Path = fl.DATA_FINN / "history"
HISTORY_JSONL: Path = HISTORY_DIR / "viewed.jsonl"


def log_view(record: dict[str, Any]) -> dict[str, Any]:
    """Append one viewed-ad record (adds ``viewed_at`` / ``viewed_ts``). Never rewrites."""
    rec = dict(record or {})
    now = datetime.now(timezone.utc)
    rec.setdefault("viewed_at", now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    rec.setdefault("viewed_ts", now.strftime("%Y-%m-%d-%H%M%S"))
    fl.ensure_dir(HISTORY_DIR)
    fl.append_jsonl(HISTORY_JSONL, rec)
    return rec


def _age_hours(viewed_at: Any) -> float | None:
    try:
        when = datetime.strptime(str(viewed_at), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    return (datetime.now(timezone.utc) - when).total_seconds() / 3600.0


def read_history(
    *,
    since_hours: float | None = None,
    match: str | None = None,
    kode: str | None = None,
    limit: int = 0,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return viewed records, newest first, filtered by age / substring / FINN-kode.

    ``path`` overrides the live log (used by ``--path`` for ad-hoc files); it is
    passed explicitly rather than by mutating the module global.
    """
    log_path = path or HISTORY_JSONL
    if not log_path.exists():
        return []
    needle = (match or "").strip().lower()
    out: list[dict[str, Any]] = []
    with log_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if kode and str(rec.get("finn_kode")) != str(kode):
                continue
            if since_hours is not None:
                age = _age_hours(rec.get("viewed_at"))
                if age is None or age > since_hours:
                    continue
            if needle:
                hay = " ".join(
                    str(rec.get(k) or "")
                    for k in ("heading", "matched_name", "card_name", "url")
                ).lower()
                if needle not in hay:
                    continue
            out.append(rec)
    out.reverse()
    return out[:limit] if limit and limit > 0 else out


def _fmt(rec: dict[str, Any]) -> str:
    kode = rec.get("finn_kode") or "?"
    heading = (rec.get("heading") or "").strip()
    matched = rec.get("matched_name") or rec.get("card_name") or ""
    finn = rec.get("finn_price_nok")
    est = rec.get("est_nok")
    bits = []
    if finn is not None:
        bits.append(f"FINN {finn} kr")
    if est is not None:
        bits.append(f"est ~{est} kr")
    tail = ("  " + " | ".join(bits)) if bits else ""
    mt = f"  -> {matched}" if matched else ""
    return f"{rec.get('viewed_at', '?')}  {kode:>10}  {heading}{mt}{tail}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Query the append-only FINN viewed-ad history.")
    parser.add_argument("--since-days", type=float, default=None, help="only records newer than N days")
    parser.add_argument("--since-hours", type=float, default=None, help="only records newer than N hours")
    parser.add_argument("--match", default=None, help="case-insensitive substring in heading / matched card / url")
    parser.add_argument("--kode", default=None, help="exact FINN-kode")
    parser.add_argument("--limit", type=int, default=0, help="max records (0 = all)")
    parser.add_argument("--json", action="store_true", help="emit JSONL instead of a table")
    parser.add_argument("--path", default=str(HISTORY_JSONL), help="history file (default: the live log)")
    args = parser.parse_args(argv)

    since_hours = args.since_hours
    if since_hours is None and args.since_days is not None:
        since_hours = args.since_days * 24.0

    log_path = Path(args.path)
    print(f"history   : {log_path}  (exists={log_path.exists()})")
    print(f"filter    : since_hours={since_hours} match={args.match!r} kode={args.kode!r} limit={args.limit}")
    print("-" * 88)

    rows = read_history(since_hours=since_hours, match=args.match, kode=args.kode,
                        limit=args.limit, path=log_path)
    print(f"{len(rows)} record(s)")
    for rec in rows:
        if args.json:
            print(json.dumps(rec, ensure_ascii=False))
        else:
            print(_fmt(rec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
