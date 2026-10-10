#!/usr/bin/env python3
"""finn_deals.py — the one-row-per-ad FINN **deal table** (Sheet-ready).

Three append-only sources are joined into a single, **deduplicated**, human-facing
table:

* the **ad archive** (``data/finn/annonser/<kode>_<slug>/<kode>.json``) — the ad
  identity: title, url, asking price, status, location, images, last-modified;
* **identify** (via :mod:`finn_identify`) — which interesting set / named card
  the ad is, and how badly Marius wants it (Tier-1 → named → Tier-2);
* **pricing** (``data/finn/matches/pricing.jsonl``) — the matched PokeWallet card,
  market value (NOK), the deal ratio, per-card coverage, and confidence.

``pricing.jsonl`` is **append-only**, so it accumulates many records per ad across
runs.  This module keeps the **best** record per FINN-kode — one with a market
value, then the most priced cards, then the newest — so a re-run never
double-counts an ad and a later empty (offline) record cannot mask an earlier good
one.

Outputs (under ``data/finn/tables/``, timestamped, never overwritten):

* ``deals_<ts>.csv`` — the full table (every column);
* ``deals_<ts>.html`` — the same table, self-contained and client-side sortable;
* ``deals_<ts>.jsonl`` — one full row per line (machine artifact);
* ``finn_sheet_<ts>.csv`` — exactly the 10 columns of the bound Sheet's FINN tab;
* ``summary_<ts>.json`` — honest coverage counts.

It also emits a **priority-ordered** ad JSONL (Tier-1 sets → named cards →
Tier-2 sets → the rest) so the budget-bound pricing pass spends its hourly calls
on what Marius wants first::

    uv run finn/finn_deals.py --emit-priority data/finn/matches/priority.jsonl
    uv run finn/finn_deals.py                      # build the table
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent))  # finn/  -> sibling modules

import finn_corpus as fcorp  # noqa: E402  (archive -> records join)
import finn_identify as fi  # noqa: E402   (intent ranking)
import finn_tables as ft  # noqa: E402     (tested CSV/HTML writers)
import finnlib as fl  # noqa: E402

DEALS_VERSION = "finn_deals/1.0.0"

DATA_FINN = fl.DATA_FINN
DEFAULT_ANNONSER = DATA_FINN / "annonser"
DEFAULT_PRICING = DATA_FINN / "matches" / "pricing.jsonl"
DEFAULT_REGISTRY = DATA_FINN / "registry" / "pokemon-kort.json"
DEFAULT_OUTDIR = DATA_FINN / "tables"

# The full, comprehensive table (CSV header order = column order).
COLUMNS = [
    "finn_kode", "title", "url", "status", "asking_price_nok", "location",
    "images", "last_modified", "intent", "intent_rank", "matched_sets",
    "matched_cards", "pk_card", "pk_set", "pk_number", "market_value_nok",
    "delta_nok", "ratio", "basis", "cards_priced", "cards_total", "coverage",
    "confidence", "partial", "notes", "first_seen", "last_seen",
]

# Exactly the bound Sheet's FINN tab (sheet/build_sheet.py::FINN_HEADER).
SHEET_COLUMNS = [
    "FINN-kode", "Title", "Price (NOK)", "Matched card", "Market price",
    "Delta", "Ratio", "Status", "First seen", "Last seen",
]

# intent_rank: 1 Tier-1 set, 2 named card, 3 Tier-2 set, 0 none.  "none" sorts last.
_INTENT_SORT = {1: 1, 2: 2, 3: 3, 0: 9}


def log(message: str) -> None:
    """Progress on stderr so ``--json`` stdout stays machine-parseable."""
    print(message, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not Path(path).is_file():
        return rows
    # JSONL is "\n"-delimited: splitlines() would also split on U+2028/U+2029,
    # which real FINN descriptions contain (see work item 0009).
    for line in Path(path).read_text(encoding="utf-8").split("\n"):
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def load_registry(path: str | Path) -> dict[str, dict[str, Any]]:
    """Return ``{finn_kode: {first_seen, last_seen, ...}}`` (or ``{}`` if absent)."""
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report, never crash the table
        log(f"WARN: registry unreadable ({exc!r}); first/last seen left blank")
        return {}
    ads = raw.get("ads") if isinstance(raw, dict) else None
    if isinstance(ads, dict):
        return {str(k): v for k, v in ads.items() if isinstance(v, dict)}
    if isinstance(ads, list):
        out: dict[str, dict] = {}
        for a in ads:
            if isinstance(a, dict) and a.get("finn_kode"):
                out[str(a["finn_kode"])] = a
        return out
    return {}


def _pricing_rank(rec: dict[str, Any]) -> tuple[int, int, str]:
    """Rank a pricing record for "best": value first, then cards priced, then newest."""
    deal = rec.get("deal") or {}
    has_value = 1 if deal.get("market_value_nok") is not None else 0
    priced = int((rec.get("card_coverage") or {}).get("priced") or 0)
    return (has_value, priced, str(rec.get("generated_at") or ""))


def latest_pricing(path: str | Path) -> dict[str, dict[str, Any]]:
    """Best pricing record per FINN-kode (append-only input, one row out per ad)."""
    best: dict[str, dict[str, Any]] = {}
    for rec in _read_jsonl(Path(path)):
        kode = str(rec.get("finn_kode") or "")
        if not kode:
            continue  # heading-only probe records have no kode -> not an ad
        cur = best.get(kode)
        if cur is None or _pricing_rank(rec) > _pricing_rank(cur):
            best[kode] = rec
    return best


# --------------------------------------------------------------------------- #
# confidence
# --------------------------------------------------------------------------- #


def card_confidence(res: dict[str, Any]) -> str | None:
    """Aggregate the confidence of the priced cards (majority rule)."""
    priced = [c for c in (res.get("cards") or []) if c.get("priced")]
    if not priced:
        return None
    confs = [c.get("confidence") for c in priced]
    n = len(confs)
    hi = sum(1 for c in confs if c == "high")
    medhi = sum(1 for c in confs if c in ("high", "medium"))
    if hi >= 0.8 * n:
        return "high"
    if medhi >= 0.8 * n:
        return "medium"
    return "low"


def row_confidence(res: dict[str, Any] | None) -> str:
    """How much to trust the market value on this row.

    A card-list sum inherits the (majority) confidence of the cards actually
    priced; a listing match keeps ``finn_price``'s listing confidence.
    """
    if not res:
        return "none"
    if (res.get("deal") or {}).get("basis") == "card_list_sum":
        return card_confidence(res) or res.get("listing_confidence") or "none"
    return res.get("listing_confidence") or "none"


# --------------------------------------------------------------------------- #
# row building
# --------------------------------------------------------------------------- #


def _matched_pk(res: dict[str, Any]) -> tuple[str, str, str]:
    """Return ``(pk_card, pk_set, pk_number)`` for the ad's market match."""
    deal = res.get("deal") or {}
    if deal.get("basis") == "card_list_sum":
        priced = [c for c in (res.get("cards") or []) if c.get("priced")]
        names: list[str] = []
        for c in priced:
            nm = c.get("pk_name") or c.get("name")
            if nm and nm not in names:
                names.append(nm)
        shown = "; ".join(names[:5])
        if len(names) > 5:
            shown += f" … (+{len(names) - 5})"
        return shown, f"{len(names)} distinct cards", ""
    best = (res.get("listing") or {}).get("best") or {}
    return (best.get("name") or "", best.get("set_name") or "",
            best.get("card_number") or "")


def build_rows(records: list[dict[str, Any]],
               pricing: dict[str, dict[str, Any]],
               registry: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """One comprehensive row per archived ad (identity + intent + price)."""
    registry = registry or {}
    rows: list[dict[str, Any]] = []
    for rec in records:
        kode = str(rec.get("finn_kode") or "")
        res = pricing.get(kode) or {}
        deal = res.get("deal") or {}
        cov = res.get("card_coverage") or {}
        ident = fi.identify_ad(rec)
        reg = registry.get(kode) or {}
        pk_card, pk_set, pk_number = _matched_pk(res) if res else ("", "", "")
        total = int(cov.get("total") or 0)
        priced = int(cov.get("priced") or 0)
        rows.append({
            "finn_kode": kode,
            "title": rec.get("title") or "",
            "url": rec.get("url") or f"https://www.finn.no/{kode}",
            "status": rec.get("status") or "",
            "asking_price_nok": rec.get("price_nok"),
            "location": rec.get("location_text") or "",
            "images": rec.get("gallery_count") or len(rec.get("image_uuids") or []),
            "last_modified": rec.get("last_modified") or "",
            "intent": ident.get("intent"),
            "intent_rank": ident.get("intent_rank"),
            "matched_sets": "; ".join(ident.get("matched_set_names") or []),
            "matched_cards": "; ".join(ident.get("matched_card_names") or []),
            "pk_card": pk_card,
            "pk_set": pk_set,
            "pk_number": pk_number,
            "market_value_nok": deal.get("market_value_nok"),
            "delta_nok": deal.get("delta_nok"),
            "ratio": deal.get("ratio"),
            "basis": deal.get("basis"),
            "cards_priced": priced if total else None,
            "cards_total": total if total else None,
            "coverage": f"{priced}/{total}" if total else "",
            "confidence": row_confidence(res) if res else "none",
            "partial": bool(res.get("partial_card_coverage")),
            "notes": "; ".join(str(f) for f in (res.get("flags") or [])),
            "first_seen": reg.get("first_seen") or "",
            "last_seen": reg.get("last_seen") or "",
        })
    return rows


def sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Interesting ads first (Tier-1 → named → Tier-2), best deal first within each."""
    def key(row: dict[str, Any]) -> tuple[int, int, float, str]:
        rank = _INTENT_SORT.get(int(row.get("intent_rank") or 0), 9)
        ratio = row.get("ratio")
        present = 0 if ratio is not None else 1
        return (rank, present, -(ratio or 0.0), str(row.get("finn_kode") or ""))
    return sorted(rows, key=key)


def sheet_rows(rows: list[dict[str, Any]]) -> list[list[Any]]:
    """Project full rows to exactly the bound Sheet's 10 FINN columns."""
    out: list[list[Any]] = []
    for r in rows:
        matched = r.get("pk_card") or ""
        if r.get("pk_set"):
            matched = f"{matched} ({r['pk_set']})" if matched else r["pk_set"]
        out.append([
            r.get("finn_kode"), r.get("title"), r.get("asking_price_nok"),
            matched, r.get("market_value_nok"), r.get("delta_nok"),
            r.get("ratio"), r.get("status"), r.get("first_seen"),
            r.get("last_seen"),
        ])
    return out


def _write_matrix_csv(path: str | Path, rows: list[list[Any]],
                      columns: list[str]) -> Path:
    """Write a header + list-of-lists as RFC-4180 CSV (blank for missing)."""
    import csv
    p = Path(path)
    fl.ensure_dir(p.parent)
    with p.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(["" if v is None else v for v in row])
    return p


# --------------------------------------------------------------------------- #
# priority ordering (for the budget-bound pricing pass)
# --------------------------------------------------------------------------- #


def priority_order(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order ads by intent: Tier-1 sets → named cards → Tier-2 sets → the rest."""
    def key(rec: dict[str, Any]) -> tuple[int, str]:
        rank = fi.identify_ad(rec).get("intent_rank") or 0
        return (_INTENT_SORT.get(rank, 9), str(rec.get("finn_kode") or ""))
    return sorted(records, key=key)


def emit_priority(records: list[dict[str, Any]], out: str | Path) -> Path:
    """Write the ad records, priority-ordered, to ``out`` (unique, never overwrites)."""
    path = fl.unique_path(out)
    fl.ensure_dir(Path(path).parent)
    for rec in priority_order(records):
        fl.append_jsonl(path, rec)
    return path


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Honest coverage counts for the table."""
    priced = [r for r in rows if r.get("market_value_nok") is not None]
    deals = [r for r in rows if r.get("ratio") is not None and r["ratio"] > 1]
    by_intent: dict[str, int] = {}
    for r in rows:
        by_intent[r.get("intent") or "?"] = by_intent.get(r.get("intent") or "?", 0) + 1
    by_conf: dict[str, int] = {}
    for r in rows:
        by_conf[r.get("confidence") or "?"] = by_conf.get(r.get("confidence") or "?", 0) + 1
    return {
        "rows": len(rows),
        "priced": len(priced),
        "with_ratio": len([r for r in rows if r.get("ratio") is not None]),
        "deals_ratio_gt_1": len(deals),
        "by_intent": by_intent,
        "by_confidence": by_conf,
    }


def build(records: list[dict[str, Any]], pricing: dict[str, dict[str, Any]],
          outdir: str | Path, *, registry: dict[str, dict[str, Any]] | None = None,
          ts: str | None = None) -> dict[str, Any]:
    """Write the deal table (CSV/HTML/JSONL), the Sheet CSV, and a summary."""
    ts = ts or fl.ts_now()
    out = fl.ensure_dir(outdir)

    rows = sort_rows(build_rows(records, pricing, registry))
    deals_csv = fl.unique_path(out / f"deals_{ts}.csv")
    deals_html = fl.unique_path(out / f"deals_{ts}.html")
    deals_jsonl = fl.unique_path(out / f"deals_{ts}.jsonl")
    sheet_csv = fl.unique_path(out / f"finn_sheet_{ts}.csv")
    summary_path = fl.unique_path(out / f"summary_{ts}.json")

    ft.write_csv(deals_csv, rows, COLUMNS)
    _write_matrix_csv(sheet_csv, sheet_rows(rows), SHEET_COLUMNS)
    deals_html.write_text(
        ft.render_html(rows, COLUMNS, title=f"FINN Pokemon deals — {ts}"),
        encoding="utf-8",
    )
    with deals_jsonl.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False))
            fh.write("\n")

    summary = {
        "deals_version": DEALS_VERSION,
        "ts": ts,
        "generated_at": fl.iso_now(),
        **summarise(rows),
        "paths": {
            "deals_csv": str(deals_csv),
            "deals_html": str(deals_html),
            "deals_jsonl": str(deals_jsonl),
            "sheet_csv": str(sheet_csv),
            "summary": str(summary_path),
        },
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--annonser", default=str(DEFAULT_ANNONSER),
                        help="ad archive root (default data/finn/annonser)")
    parser.add_argument("--pricing", default=str(DEFAULT_PRICING),
                        help="pricing JSONL (default data/finn/matches/pricing.jsonl)")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY),
                        help="discovery registry (for first/last seen)")
    parser.add_argument("--outdir", default=str(DEFAULT_OUTDIR),
                        help="output dir (default data/finn/tables)")
    parser.add_argument("--ts", default=None, help="force the filename timestamp")
    parser.add_argument("--emit-priority", metavar="FILE", default=None,
                        help="write ad records priority-ordered to FILE and exit")
    parser.add_argument("--json", action="store_true",
                        help="print the summary as JSON on stdout")
    args = parser.parse_args(argv)

    records, problems = fcorp.collect(Path(args.annonser))
    log("=" * 88)
    log(f"FINN deals  |  archived={len(records)}  problems={len(problems)}")
    log("=" * 88)
    for p in problems:
        log(f"  PROBLEM {p['folder']}: {p['error']}")

    if args.emit_priority:
        path = emit_priority(records, Path(args.emit_priority))
        log(f"  priority -> {path}  ({len(records)} ads, Tier-1 first)")
        return 0

    pricing = latest_pricing(args.pricing)
    registry = load_registry(args.registry)
    summary = build(records, pricing, args.outdir, registry=registry, ts=args.ts)

    log(f"  priced ads      : {summary['priced']}/{summary['rows']}")
    log(f"  with deal ratio : {summary['with_ratio']}  (ratio>1: {summary['deals_ratio_gt_1']})")
    log(f"  by intent       : {summary['by_intent']}")
    log(f"  by confidence   : {summary['by_confidence']}")
    for key, val in summary["paths"].items():
        log(f"  {key:12s} -> {val}")
    log("=" * 88)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
