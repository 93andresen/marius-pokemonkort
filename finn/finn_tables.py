#!/usr/bin/env python3
"""Assemble ``pricing.jsonl`` records into the program's headline tables.

This stage is **pure formatting** — it makes no network calls and never touches
the cache.  It reads the append-only records produced by ``finn_price.py`` and
writes two human-facing views under ``data/finn/tables/``:

* a **listings table** — one row per ad, best deal first, with the deal ratio
  (``market_value_nok / asking_price_nok``) next to the seller's asking price;
* a **cards table** — one row per enumerated card across all ads.

Both are emitted as RFC-4180 **CSV** *and* the listings also as a single
**self-contained HTML** page whose header cells sort the table on click (numeric
vs text detected per cell, works from ``file://``).  Missing numbers are left
blank in CSV and rendered as an em-dash in HTML — never fabricated as ``0``.

Run::

    uv run finn/finn_tables.py --from-jsonl data/finn/matches/pricing.jsonl
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent))  # finn/

import finnlib as fl  # noqa: E402

TABLES_VERSION = "finn_tables/1.0.0"

DATA_FINN = fl.DATA_FINN
DEFAULT_JSONL = DATA_FINN / "matches" / "pricing.jsonl"
DEFAULT_OUTDIR = DATA_FINN / "tables"

MISSING_HTML = "\u2014"  # em dash

# Explicit column order (also the CSV header order).
LISTING_COLUMNS = [
    "finn_kode", "heading", "url", "intent_rank", "intent",
    "asking_price_nok", "market_value_nok", "delta_nok", "ratio", "basis",
    "cards_total", "cards_priced", "partial_coverage", "listing_confidence",
    "cache_hit", "flags",
]

CARD_COLUMNS = [
    "finn_kode", "name", "count", "variants", "line_index", "query",
    "confidence", "score", "pk_id", "pk_name", "pk_set_name", "pk_card_number",
    "price_native", "price_currency", "price_source",
    "unit_market_value_nok", "market_value_nok", "priced",
]


def log(message: str) -> None:
    """Progress goes to stderr so ``--json`` stdout stays machine-parseable."""
    print(message, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- #
# flat-row projection
# --------------------------------------------------------------------------- #


def listing_row(res: dict[str, Any]) -> dict[str, Any]:
    """Flatten one pricing record into the single listings-table row."""
    deal = res.get("deal") or {}
    ident = res.get("identify") or {}
    cov = res.get("card_coverage") or {}
    flags = res.get("flags") or []
    return {
        "finn_kode": res.get("finn_kode"),
        "heading": res.get("heading"),
        "url": res.get("url"),
        "intent_rank": ident.get("intent_rank"),
        "intent": ident.get("intent"),
        "asking_price_nok": deal.get("asking_price_nok"),
        "market_value_nok": deal.get("market_value_nok"),
        "delta_nok": deal.get("delta_nok"),
        "ratio": deal.get("ratio"),
        "basis": deal.get("basis"),
        "cards_total": cov.get("total"),
        "cards_priced": cov.get("priced"),
        "partial_coverage": res.get("partial_card_coverage"),
        "listing_confidence": res.get("listing_confidence"),
        "cache_hit": res.get("cache_hit"),
        "flags": "; ".join(str(f) for f in flags),
    }


def card_rows(res: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand one pricing record's ``cards[]`` into flat cards-table rows."""
    kode = res.get("finn_kode")
    out: list[dict[str, Any]] = []
    for card in res.get("cards") or []:
        variants = card.get("variants") or []
        out.append({
            "finn_kode": kode,
            "name": card.get("name"),
            "count": card.get("count"),
            "variants": ", ".join(str(v) for v in variants),
            "line_index": card.get("line_index"),
            "query": card.get("query"),
            "confidence": card.get("confidence"),
            "score": card.get("score"),
            "pk_id": card.get("pk_id"),
            "pk_name": card.get("pk_name"),
            "pk_set_name": card.get("pk_set_name"),
            "pk_card_number": card.get("pk_card_number"),
            "price_native": card.get("price_native"),
            "price_currency": card.get("price_currency"),
            "price_source": card.get("price_source"),
            "unit_market_value_nok": card.get("unit_market_value_nok"),
            "market_value_nok": card.get("market_value_nok"),
            "priced": card.get("priced"),
        })
    return out


# --------------------------------------------------------------------------- #
# ordering
# --------------------------------------------------------------------------- #


def sort_listings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Best deal first: ``ratio`` descending, missing ratios last, then stable."""

    def key(row: dict[str, Any]) -> tuple[int, float, str, str]:
        ratio = row.get("ratio")
        present = 0 if ratio is not None else 1
        return (present, -(ratio if ratio is not None else 0.0),
                str(row.get("finn_kode") or ""), str(row.get("heading") or ""))

    return sorted(rows, key=key)


# --------------------------------------------------------------------------- #
# cell rendering
# --------------------------------------------------------------------------- #


def _csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _html_cell(value: Any) -> str:
    if value is None or value == "":
        return MISSING_HTML
    if isinstance(value, bool):
        return "true" if value else "false"
    return html.escape(str(value))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _column_is_numeric(rows: list[dict[str, Any]], column: str) -> bool:
    """A column sorts numerically iff every present cell is a number."""
    seen = False
    for row in rows:
        value = row.get(column)
        if value is None or value == "":
            continue
        if not _is_number(value):
            return False
        seen = True
    return seen


# --------------------------------------------------------------------------- #
# writers
# --------------------------------------------------------------------------- #


def write_csv(path: str | Path, rows: list[dict[str, Any]],
              columns: list[str]) -> Path:
    """Write ``rows`` as RFC-4180 CSV with an explicit header, atomically."""
    p = Path(path)
    fl.ensure_dir(p.parent)
    with p.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([_csv_cell(row.get(col)) for col in columns])
    return p


_HTML_STYLE = """
  body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         margin: 1.5rem; color: #17202a; }
  h1 { font-size: 1.25rem; }
  table { border-collapse: collapse; font-size: 0.86rem; }
  th, td { border: 1px solid #d5d8dc; padding: 4px 8px; text-align: left;
           white-space: nowrap; }
  th { position: sticky; top: 0; background: #eef2f6; cursor: pointer;
       user-select: none; }
  th[data-dir="asc"]::after { content: " \\25B2"; color: #566573; }
  th[data-dir="desc"]::after { content: " \\25BC"; color: #566573; }
  tr:nth-child(even) td { background: #fafbfc; }
"""

_HTML_SCRIPT = """<script>
function sortTable(th) {
  var table = th.closest('table');
  var head = th.parentNode;
  var idx = Array.prototype.indexOf.call(head.children, th);
  var type = th.getAttribute('data-type');
  var tbody = table.tBodies[0];
  var rows = Array.prototype.slice.call(tbody.rows);
  var dir = th.getAttribute('data-dir') === 'asc' ? 'desc' : 'asc';
  Array.prototype.forEach.call(head.children, function (h) {
    h.removeAttribute('data-dir');
  });
  th.setAttribute('data-dir', dir);
  rows.sort(function (a, b) {
    var x = cellValue(a.cells[idx], type);
    var y = cellValue(b.cells[idx], type);
    if (x === null && y === null) { return 0; }
    if (x === null) { return 1; }
    if (y === null) { return -1; }
    if (x < y) { return dir === 'asc' ? -1 : 1; }
    if (x > y) { return dir === 'asc' ? 1 : -1; }
    return 0;
  });
  rows.forEach(function (r) { tbody.appendChild(r); });
}
function cellValue(td, type) {
  var text = td.textContent.trim();
  if (text === '' || text === '\\u2014') { return null; }
  if (type === 'number') {
    var n = parseFloat(text);
    return isNaN(n) ? null : n;
  }
  return text.toLowerCase();
}
</script>"""


def render_html(rows: list[dict[str, Any]], columns: list[str], *,
                title: str = "FINN Pokemon prices") -> str:
    """One self-contained, client-side-sortable HTML page (no external assets)."""
    numeric = {col: _column_is_numeric(rows, col) for col in columns}
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{html.escape(title)}</title>",
        f"<style>{_HTML_STYLE}</style>",
        "</head>",
        "<body>",
        f"<h1>{html.escape(title)}</h1>",
        f"<p>{len(rows)} row(s) &middot; click a header to sort</p>",
        "<table>",
        "<thead><tr>",
    ]
    for i, col in enumerate(columns):
        ctype = "number" if numeric[col] else "text"
        label = html.escape(col)
        parts.append(
            f'<th data-col="{i}" data-type="{ctype}" '
            f'onclick="sortTable(this)">{label}</th>'
        )
    parts.append("</tr></thead>")
    parts.append("<tbody>")
    for row in rows:
        parts.append("<tr>")
        for col in columns:
            parts.append(f"<td>{_html_cell(row.get(col))}</td>")
        parts.append("</tr>")
    parts.append("</tbody>")
    parts.append("</table>")
    parts.append(_HTML_SCRIPT)
    parts.append("</body></html>")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #


def build(records: list[dict[str, Any]], outdir: str | Path, *,
          ts: str | None = None) -> dict[str, Any]:
    """Write ``listings_<ts>.csv|html`` + ``cards_<ts>.csv``; return the paths."""
    ts = ts or fl.ts_now()
    out = fl.ensure_dir(outdir)

    listings = sort_listings([listing_row(r) for r in records])
    cards: list[dict[str, Any]] = []
    for rec in records:
        cards.extend(card_rows(rec))

    listings_csv = fl.unique_path(out / f"listings_{ts}.csv")
    listings_html = fl.unique_path(out / f"listings_{ts}.html")
    cards_csv = fl.unique_path(out / f"cards_{ts}.csv")

    write_csv(listings_csv, listings, LISTING_COLUMNS)
    write_csv(cards_csv, cards, CARD_COLUMNS)
    listings_html.write_text(
        render_html(listings, LISTING_COLUMNS,
                    title=f"FINN Pokemon listings — {ts}"),
        encoding="utf-8",
    )

    return {
        "tables_version": TABLES_VERSION,
        "ts": ts,
        "listings": len(listings),
        "cards": len(cards),
        "paths": {
            "listings_csv": str(listings_csv),
            "listings_html": str(listings_html),
            "cards_csv": str(cards_csv),
        },
    }


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
    parser.add_argument("--from-jsonl", default=str(DEFAULT_JSONL),
                        help="pricing records (JSONL) to tabulate")
    parser.add_argument("--outdir", default=str(DEFAULT_OUTDIR),
                        help="output directory for the table files")
    parser.add_argument("--ts", default=None,
                        help="timestamp for filenames (default: now)")
    parser.add_argument("--json", action="store_true",
                        help="print the summary as JSON on stdout")
    args = parser.parse_args(argv)

    src = Path(args.from_jsonl)
    if not src.exists():
        log(f"ERROR: input not found: {src}")
        return 2

    records = _read_jsonl(src)
    summary = build(records, args.outdir, ts=args.ts)

    log("=" * 88)
    log(f"FINN tables  |  {len(records)} record(s)  |  ts={summary['ts']}")
    log("=" * 88)
    log(f"  listings_csv  -> {summary['paths']['listings_csv']}  "
        f"({summary['listings']} rows)")
    log(f"  listings_html -> {summary['paths']['listings_html']}")
    log(f"  cards_csv     -> {summary['paths']['cards_csv']}  "
        f"({summary['cards']} rows)")
    log("=" * 88)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
