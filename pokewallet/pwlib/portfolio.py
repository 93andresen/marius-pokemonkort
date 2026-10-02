"""Parse and normalise the Collectr portfolio export.

The export is a CSV whose columns are (see getcollectr/*.csv):

    Portfolio Name, Category, Set, Product Name, Card Number, Rarity, Variance,
    Grade, Card Condition, Average Cost Paid, Quantity,
    Market Price (As of YYYY-MM-DD), Price Override, Watchlist, Date Added, Notes

Values are in NOK; large numbers arrive quoted with comma thousands
(e.g. ``"1,018.31"``) so money parsing strips commas.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .util import to_float

SET_COL = "Set"
NAME_COL = "Product Name"
NUMBER_COL = "Card Number"
QTY_COL = "Quantity"
COST_COL = "Average Cost Paid"
MARKET_COL_PREFIX = "Market Price"
GRADE_COL = "Grade"
VARIANCE_COL = "Variance"
RARITY_COL = "Rarity"
CONDITION_COL = "Card Condition"
WATCHLIST_COL = "Watchlist"
DATE_ADDED_COL = "Date Added"
PORTFOLIO_COL = "Portfolio Name"
CATEGORY_COL = "Category"
NOTES_COL = "Notes"


def read_rows(path: str | Path) -> tuple[list[str], list[dict]]:
    """Return ``(fieldnames, rows)`` from a Collectr CSV."""
    p = Path(path)
    with p.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = [dict(r) for r in reader]
        return list(reader.fieldnames or []), rows


def market_column(fieldnames: list[str]) -> str | None:
    """Find the dated 'Market Price (...)' column name."""
    for name in fieldnames:
        if name.startswith(MARKET_COL_PREFIX):
            return name
    return None


def number_norm(raw: Any) -> str:
    """Normalise a card number for matching across naming schemes.

    ``"090/066"`` → ``"90"``, ``"005"`` → ``"5"``, ``"TG01"`` → ``"TG01"``.
    Only the numerator (before ``/``) is used.
    """
    text = str(raw or "").strip()
    numerator = text.split("/")[0].strip()
    stripped = numerator.lstrip("0")
    return (stripped or "0").lower()


def number_variants(raw: Any) -> set[str]:
    """All plausible keys for a card number, for tolerant matching."""
    text = str(raw or "").strip()
    numerator = text.split("/")[0].strip()
    variants = {text.lower(), numerator.lower(), number_norm(text)}
    return {v for v in variants if v}


def parse_quantity(raw: Any) -> int:
    value = to_float(raw)
    if value is None:
        return 1
    return int(value)


def parse_money(raw: Any) -> float | None:
    return to_float(raw)


def distinct_sets(rows: list[dict]) -> list[str]:
    seen: dict[str, None] = {}
    for row in rows:
        name = (row.get(SET_COL) or "").strip()
        if name:
            seen.setdefault(name, None)
    return sorted(seen)
