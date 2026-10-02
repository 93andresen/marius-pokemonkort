#!/usr/bin/env python3
"""Build the Google-Sheet payload from local captures (no network).

Reads the newest PokeWallet snapshot + resolved portfolio + set index + rate log,
computes every tab described in PROJECT-PLAN.md §8, and writes a single payload
JSON (`sheet/out/sheet_payload_<ts>.json`) plus per-tab CSV previews.

The actual push to Google Sheets is done through the google-sheets MCP server
(the only authenticated write path); this script is the reproducible *source*
of the values so a re-run reproduces the exact same sheet contents.

Run:
    uv run sheet/build_sheet.py            # write payload + CSV previews
    uv run sheet/build_sheet.py --print    # also print tab sizes

Nothing here is deleted or overwritten: every run writes a new timestamped
payload and a `latest/` copy.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data" / "pokewallet"
SNAP_DIR = DATA / "snapshots"
SETS_DIR = DATA / "sets"
OUT_DIR = Path(__file__).resolve().parent / "out"
RATE_LOG = REPO / "logs" / "ratelog.csv"
RESOLVED_GLOB = str(DATA / "resolved_portfolio_*.csv")

# --- currency assumptions (documented on the Config tab; edit freely) --------
USD_NOK = 10.80
EUR_NOK = 11.70

# --------------------------------------------------------------------------- #


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")


def latest(pattern: str) -> Path | None:
    matches = sorted(glob.glob(pattern))
    return Path(matches[-1]) if matches else None


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = [dict(r) for r in reader]
        return list(reader.fieldnames or []), rows


def fnum(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def inum(value: object) -> int | None:
    f = fnum(value)
    return None if f is None else int(f)


def truthy(value: object) -> bool:
    return str(value).strip().lower() in ("true", "1", "yes", "true.")


# --------------------------------------------------------------------------- #
# Tab builders
# --------------------------------------------------------------------------- #

COLLECTION_HEADER = [
    "Row", "Set", "Product Name", "Number", "Rarity", "Variance", "Grade",
    "Condition", "Qty", "Avg Cost (NOK)", "Collectr Market (NOK)",
    "Collectr Value (NOK)", "TCG Market (USD)", "CMK Trend (EUR)",
    "API Value (NOK)", "Price Source", "Found", "Served From", "Match Method",
    "PK Name", "PK Set", "Watchlist", "Date Added",
    # --- derived / colour-coded signal columns (see the Apps Script for the
    #     conditional-format rules that paint these green/red) ---
    "Cost Basis (NOK)", "P&L vs Cost (NOK)", "vs Collectr %",
    "Move % (vs first seen)", "Verdict",
]

# Section-label rows deliberately start with "▸" (U+25B8) instead of "===";
# a leading "=" makes Google Sheets parse the cell as a formula → "#ERROR!".
SECTION = "▸"


def api_value_nok(qty: int, tcg_market: float | None, cmk_trend: float | None) -> float | None:
    if tcg_market is not None:
        return round(qty * tcg_market * USD_NOK, 2)
    if cmk_trend is not None:
        return round(qty * cmk_trend * EUR_NOK, 2)
    return None


def build_move_map(jsonl: Path) -> dict[str, dict]:
    """``pk_id`` → first-seen vs latest price summary, keyed on the stable card id.

    Used by the Collection tab's ``Move %`` / ``Verdict`` columns so each row can
    show whether *that card* has gone up or down since we first saw it — the
    primary "am I in the green?" signal for a card we haven't paid for.
    """
    if not jsonl.exists():
        return {}
    first: dict[str, tuple[float, str]] = {}
    last: dict[str, tuple[float, str, dict]] = {}
    with jsonl.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not truthy(rec.get("found")):
                continue
            key = rec.get("pk_id")
            if not key:
                continue
            price = fnum(rec.get("tcg_market"))
            if price is None:
                price = fnum(rec.get("cmk_trend"))
            if price is None:
                continue
            ts = str(rec.get("run_ts_utc") or "")
            if key not in first or ts < first[key][1]:
                first[key] = (price, ts)
            if key not in last or ts >= last[key][1]:
                last[key] = (price, ts, rec)
    out: dict[str, dict] = {}
    for key, (p_last, ts_last, rec) in last.items():
        p_first, ts_first = first[key]
        out[key] = {
            "move_pct": round(100 * (p_last - p_first) / p_first, 2) if p_first else None,
            "first": p_first,
            "last": p_last,
            "delta": round(p_last - p_first, 2),
            "ts_first": ts_first,
            "ts_last": ts_last,
            "set": rec.get("set") or "",
            "product_name": rec.get("product_name") or "",
            "number": rec.get("number") or "",
        }
    return out


def verdict_of(vs_collectr: float | None, move_pct: float | None) -> str:
    """One-word colour verdict. Green = up, Red = down, Yellow = flat, White = no data."""
    signal = vs_collectr if vs_collectr is not None else move_pct
    if signal is None:
        return "⚪ No data"
    if signal > 0.5:
        return "🟢 Up"
    if signal < -0.5:
        return "🔴 Down"
    return "🟡 Flat"


def build_collection(snap_rows: list[dict], move_map: dict[str, dict]) -> list[list]:
    out: list[list] = []
    for r in snap_rows:
        qty = inum(r.get("quantity")) or 1
        cm = fnum(r.get("collectr_market_nok"))
        cost = fnum(r.get("avg_cost_paid_nok"))
        tcg = fnum(r.get("tcg_market"))
        cmk = fnum(r.get("cmk_trend"))
        collectr_value = round(qty * cm, 2) if cm is not None else None
        api_val = api_value_nok(qty, tcg, cmk)
        cost_basis = round(qty * cost, 2) if (cost is not None and cost > 0) else None
        pnl = round(api_val - cost_basis, 2) if (api_val is not None and cost_basis) else None
        vs_collectr = (
            round(100 * (api_val - collectr_value) / collectr_value, 2)
            if (api_val is not None and collectr_value) else None
        )
        mv = move_map.get(r.get("pk_id") or "")
        move_pct = mv["move_pct"] if mv else None
        out.append([
            inum(r.get("row_index")),
            r.get("set") or "",
            r.get("product_name") or "",
            r.get("number") or "",
            r.get("rarity") or "",
            r.get("variance") or "",
            r.get("grade") or "",
            r.get("condition") or "",
            qty,
            cost if cost is not None else "",
            cm if cm is not None else "",
            collectr_value if collectr_value is not None else "",
            tcg if tcg is not None else "",
            cmk if cmk is not None else "",
            api_val if api_val is not None else "",
            r.get("price_source") or "",
            r.get("found") or "",
            r.get("served_from") or "",
            r.get("match_method") or "",
            r.get("pk_name") or "",
            r.get("pk_set_name") or "",
            r.get("watchlist") or "",
            r.get("date_added") or "",
            cost_basis if cost_basis is not None else "",
            pnl if pnl is not None else "",
            vs_collectr if vs_collectr is not None else "",
            move_pct if move_pct is not None else "",
            verdict_of(vs_collectr, move_pct),
        ])
    return out


SNAPSHOT_HEADER = [
    "run_id", "run_ts_utc", "row_index", "set_id", "number_norm", "product_name",
    "set", "number", "pk_id", "pk_name", "pk_set_code", "pk_set_name",
    "tcg_market", "tcg_low", "tcg_high", "cmk_trend", "cmk_avg", "cmk_low",
    "price_source", "found", "served_from", "match_method",
]


def build_snapshots(jsonl: Path) -> list[list]:
    """Flatten the append-only JSONL into one row per card per run."""
    rows: list[list] = []
    if not jsonl.exists():
        return rows
    with jsonl.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows.append([rec.get(col, "") for col in SNAPSHOT_HEADER])
    return rows


def build_sets(set_rows: list[dict]) -> list[list]:
    header = ["name", "set_code", "set_id", "language", "card_count", "number_count", "release_date"]
    return [[r.get(c, "") for c in header] for r in set_rows]


def build_coverage(snap_rows: list[dict]) -> tuple[list[list], list[list]]:
    total = len(snap_rows)
    found = [r for r in snap_rows if truthy(r.get("found"))]
    missing = [r for r in snap_rows if not truthy(r.get("found"))]

    def tally(key: str) -> list[list]:
        counts: dict[str, int] = {}
        for r in snap_rows:
            k = (r.get(key) or "(blank)").strip() or "(blank)"
            counts[k] = counts.get(k, 0) + 1
        return [[k, v] for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    summary = [
        ["Metric", "Value"],
        ["Rows in portfolio", total],
        ["Rows with a price", len(found)],
        ["Rows without a price", len(missing)],
        ["Coverage %", round(100 * len(found) / total, 1) if total else 0],
        ["", ""],
        [f"{SECTION} price_source", ""],
        *tally("price_source"),
        ["", ""],
        [f"{SECTION} served_from", ""],
        *tally("served_from"),
        ["", ""],
        [f"{SECTION} match_method", ""],
        *tally("match_method"),
    ]
    missing_rows = [
        [r.get("row_index"), r.get("set"), r.get("product_name"), r.get("number"),
         r.get("served_from"), r.get("match_method"), r.get("set_id")]
        for r in missing
    ]
    return summary, missing_rows


def build_movers(jsonl: Path) -> list[list]:
    """First-seen vs latest price per card, using the JSONL history."""
    if not jsonl.exists():
        return []
    first: dict[tuple, tuple[float, str, dict]] = {}
    last: dict[tuple, tuple[float, str, dict]] = {}
    with jsonl.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not truthy(rec.get("found")):
                continue
            price = fnum(rec.get("tcg_market"))
            if price is None:
                price = fnum(rec.get("cmk_trend"))
            if price is None:
                continue
            # Key on the stable pk_id so we never compare a (pre-fix) wrong
            # match against the card it *should* have matched.
            key = rec.get("pk_id") or (rec.get("set_id"), rec.get("number_norm"))
            ts = str(rec.get("run_ts_utc") or "")
            if key not in first or ts < first[key][1]:
                first[key] = (price, ts, rec)
            if key not in last or ts >= last[key][1]:
                last[key] = (price, ts, rec)

    out: list[list] = []
    for key, (p_last, ts_last, rec_last) in last.items():
        if key not in first:
            continue
        p_first, ts_first, _ = first[key]
        if p_first == p_last:
            continue
        delta = round(p_last - p_first, 2)
        pct = round(100 * (p_last - p_first) / p_first, 2) if p_first else ""
        out.append([
            rec_last.get("set"), rec_last.get("product_name"), rec_last.get("number"),
            p_first, p_last, delta, pct, ts_first, ts_last, rec_last.get("price_source"),
        ])
    out.sort(key=lambda row: (row[6] if isinstance(row[6], (int, float)) else 0), reverse=True)
    return out


def build_dashboard(snap_rows: list[dict], set_rows: list[dict], snap_count: int,
                    move_map: dict[str, dict]) -> list[list]:
    total = len(snap_rows)
    found = [r for r in snap_rows if truthy(r.get("found"))]
    qty_total = sum((inum(r.get("quantity")) or 1) for r in snap_rows)

    collectr_total = 0.0
    api_total = 0.0
    for r in snap_rows:
        qty = inum(r.get("quantity")) or 1
        cm = fnum(r.get("collectr_market_nok"))
        if cm is not None:
            collectr_total += qty * cm
        av = api_value_nok(qty, fnum(r.get("tcg_market")), fnum(r.get("cmk_trend")))
        if av is not None:
            api_total += av

    vs_collectr_total = (
        round(100 * (api_total - collectr_total) / collectr_total, 2) if collectr_total else None
    )

    signals = [v for v in move_map.values() if v.get("move_pct") is not None]
    up = [v for v in signals if v["move_pct"] > 0]
    down = [v for v in signals if v["move_pct"] < 0]
    best = max(signals, key=lambda v: v["move_pct"]) if signals else None
    worst = min(signals, key=lambda v: v["move_pct"]) if signals else None

    top = sorted(
        snap_rows,
        key=lambda r: (inum(r.get("quantity")) or 1) * (fnum(r.get("collectr_market_nok")) or 0),
        reverse=True,
    )[:15]

    coverage = round(100 * len(found) / total, 1) if total else 0

    rows: list[list] = [
        ["Pokémon Portfolio — Dashboard"],
        ["Generated (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")],
        [],
        [f"{SECTION} HOLDINGS"],
        ["Distinct rows", total],
        ["Total card quantity", qty_total],
        ["Rows with an API price", len(found)],
        ["Price coverage %", coverage],
        [],
        [f"{SECTION} VALUE (NOK)"],
        ["Collectr market total", round(collectr_total, 2)],
        [f"API-priced total (USD {USD_NOK} / EUR {EUR_NOK})", round(api_total, 2)],
        ["API vs Collectr %", vs_collectr_total if vs_collectr_total is not None else ""],
        [],
        [f"{SECTION} PRICE SIGNALS (since first seen)"],
        ["Cards up", len(up)],
        ["Cards down", len(down)],
        ["Biggest gainer", best["product_name"] if best else "",
         best["move_pct"] if best else ""],
        ["Biggest loser", worst["product_name"] if worst else "",
         worst["move_pct"] if worst else ""],
        [],
        [f"{SECTION} CATALOG"],
        ["Sets in catalog", len(set_rows)],
        ["Snapshot records captured", snap_count],
        [],
        [f"{SECTION} LIVE FORMULAS (self-updating)"],
        ["Collection rows", "=COUNTA(Collection!C2:C)"],
        ["Collectr value total", "=SUM(Collection!L2:L)"],
        ["API value total", "=SUM(Collection!O2:O)"],
        [],
        [f"{SECTION} TOP 15 BY COLLECTR VALUE"],
        ["Set", "Product", "Number", "Qty", "Collectr (NOK)", "Collectr Value (NOK)"],
    ]
    for r in top:
        qty = inum(r.get("quantity")) or 1
        cm = fnum(r.get("collectr_market_nok"))
        rows.append([
            r.get("set"), r.get("product_name"), r.get("number"), qty,
            cm if cm is not None else "", round(qty * cm, 2) if cm is not None else "",
        ])
    rows += [
        [],
        [f"{SECTION} LEGEND"],
        ["🟢 Up / above reference", "in the green", "gain or favourable"],
        ["🔴 Down / below reference", "in the red", "loss or unfavourable"],
        ["🟡 Flat (±0.5%)", "", "little or no movement"],
        ["⚪ No data", "", "no price/signal captured yet"],
        [],
        ["Sources: PokeWallet API (TCGPlayer USD, CardMarket EUR) × fixed FX; Collectr export."],
        ["Colours applied by the bound Apps Script (menu: 📊 Portfolio ▸ Format everything)."],
    ]
    return rows


def build_config(sheet_id: str, apps_script_id: str) -> list[list]:
    return [
        ["Key", "Value", "Note"],
        ["SHEET_ID", sheet_id, "canonical home = top of AGENTS.md"],
        ["APPS_SCRIPT_ID", apps_script_id, ""],
        ["POKEWALLET_BASE_URL", "https://api.pokewallet.io", ""],
        ["HOURLY_LIMIT", 100, "free plan"],
        ["DAILY_LIMIT", 1000, "free plan"],
        ["MIN_HOUR_REMAINING", 5, "safety floor left for interactive use"],
        ["MIN_DAY_REMAINING", 20, "safety floor"],
        ["USD_NOK", USD_NOK, "edit to update API->NOK conversion"],
        ["EUR_NOK", EUR_NOK, "edit to update API->NOK conversion"],
        ["FRESH_HOURS", 20, "fetcher serves cached prices younger than this"],
        ["Generated (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), ""],
    ]


def build_ratelog() -> list[list]:
    if not RATE_LOG.exists():
        return []
    header = ["timestamp_utc", "endpoint", "path", "query", "status",
              "remaining_hour", "remaining_day", "ok", "error"]
    _, rows = read_csv(RATE_LOG)
    return [[r.get(col, "") for col in header] for r in rows[-200:]]


# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print", dest="do_print", action="store_true",
                        help="print per-tab row counts after writing")
    args = parser.parse_args(argv)

    snap_csv = latest(str(SNAP_DIR / "snapshot_*.csv"))
    resolved_csv = latest(RESOLVED_GLOB)
    sets_csv = latest(str(SETS_DIR / "sets_*.csv"))
    jsonl = SNAP_DIR / "portfolio_prices.jsonl"

    if snap_csv is None or sets_csv is None:
        print("[build_sheet] ERROR: missing snapshot or sets CSV", file=sys.stderr)
        return 2

    print(f"[build_sheet] snapshot : {snap_csv.name}")
    print(f"[build_sheet] resolved : {resolved_csv.name if resolved_csv else '(none)'}")
    print(f"[build_sheet] sets     : {sets_csv.name}")
    print(f"[build_sheet] jsonl    : {jsonl.name} ({'present' if jsonl.exists() else 'MISSING'})")

    _, snap_rows = read_csv(snap_csv)
    _, set_rows = read_csv(sets_csv)
    snap_records = build_snapshots(jsonl)
    rate_rows = build_ratelog()
    coverage_summary, coverage_missing = build_coverage(snap_rows)
    move_map = build_move_map(jsonl)
    print(f"[build_sheet] signals : {len(move_map)} cards with >=1 price to compare")

    # import config lazily so the script works even if pwlib imports change
    sys.path.insert(0, str(REPO / "pokewallet"))
    try:
        from pwlib import config as pwconfig  # type: ignore
        sheet_id = pwconfig.SHEET_ID
        apps_script_id = pwconfig.APPS_SCRIPT_ID
    except Exception as exc:  # noqa: BLE001 - we want to see the failure
        print(f"[build_sheet] WARN: could not import pwlib.config ({exc}); using defaults")
        sheet_id = "13TfMos8hP4zT3-Tf92F7ZE0hJ2r7cKJdEqvdj0gvtpM"
        apps_script_id = "1zuV63oR_FZN1NRxlpgsrx5cFUuPc3p4ZgR2_pEZ8GZvJwvZEj6y2yUtr"

    tabs: dict[str, dict] = {
        "Dashboard": {"header": [],
                      "rows": build_dashboard(snap_rows, set_rows, len(snap_records), move_map)},
        "Collection": {"header": COLLECTION_HEADER, "rows": build_collection(snap_rows, move_map)},
        "PriceSnapshots": {"header": SNAPSHOT_HEADER, "rows": snap_records},
        "Sets": {"header": ["name", "set_code", "set_id", "language", "card_count",
                            "number_count", "release_date"], "rows": build_sets(set_rows)},
        "Movers": {"header": ["Set", "Product", "Number", "First", "Latest", "Delta",
                              "Delta %", "First seen (UTC)", "Latest (UTC)", "Source"],
                   "rows": build_movers(jsonl)},
        # Coverage/Config rows already begin with their own header row (the
        # builders emit it), so keep `header` empty to avoid a duplicate row.
        "Coverage": {"header": [], "rows": coverage_summary},
        "CoverageMissing": {"header": ["Row", "Set", "Product", "Number", "Served From",
                                       "Match Method", "Set ID"], "rows": coverage_missing},
        "Config": {"header": [], "rows": build_config(sheet_id, apps_script_id)},
        "RateLog": {"header": ["timestamp_utc", "endpoint", "path", "query", "status",
                               "remaining_hour", "remaining_day", "ok", "error"], "rows": rate_rows},
        "FINN": {"header": ["FINN-kode", "Title", "Price (NOK)", "Matched card", "Market price",
                            "Delta", "Status", "First seen", "Last seen"],
                 "rows": []},
    }

    stamp = utc_stamp()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "tabs": tabs}
    payload_path = OUT_DIR / f"sheet_payload_{stamp}.json"
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    latest_dir = OUT_DIR / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    (latest_dir / "sheet_payload.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    json_dir = latest_dir / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    total_cells = 0
    for name, tab in tabs.items():
        with (latest_dir / f"{name}.csv").open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            if tab["header"]:
                writer.writerow(tab["header"])
            writer.writerows(tab["rows"])
        # JSONL of rows (one compact JSON array per line) for exact MCP pasting.
        with (json_dir / f"{name}.jsonl").open("w", encoding="utf-8") as fh:
            if tab["header"]:
                fh.write(json.dumps(tab["header"], ensure_ascii=False) + "\n")
            for row in tab["rows"]:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        total_cells += len(tab["rows"]) * (len(tab["header"]) or 1)

    print(f"[build_sheet] wrote {payload_path}")
    print(f"[build_sheet] tabs      : {len(tabs)}")
    print(f"[build_sheet] total rows: {sum(len(t['rows']) for t in tabs.values())}")
    if args.do_print:
        for name, tab in tabs.items():
            print(f"    {name:<18} rows={len(tab['rows']):>5}  cols={len(tab['header'])}")
    print(f"[build_sheet] approx cells: {total_cells}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
