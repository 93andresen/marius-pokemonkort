"""Small, dependency-free utilities shared by the PokeWallet tooling.

Design rules encoded here:
- timestamps use the house format ``%Y-%m-%d-%H%M%S`` (lexically sortable);
- writing a file NEVER overwrites an existing one (a numeric suffix is added);
- appends (JSONL / CSV) are flushed immediately so a crash loses nothing.
"""

from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

TS_FORMAT = "%Y-%m-%d-%H%M%S"


# --- time ------------------------------------------------------------------
def now_ts() -> str:
    """House-format local timestamp, e.g. ``2026-10-02-153312``."""
    return datetime.now().strftime(TS_FORMAT)


def utc_iso() -> str:
    """ISO-8601 UTC timestamp with a trailing ``Z``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- strings ---------------------------------------------------------------
def slugify(value: Any, maxlen: int = 60) -> str:
    """Filesystem-safe slug; never empty."""
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip())
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:maxlen] or "none"


# --- paths -----------------------------------------------------------------
def ensure_dir(path: os.PathLike[str] | str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def unique_path(path: os.PathLike[str] | str) -> Path:
    """Return ``path`` if free, otherwise ``stem-2.ext``, ``stem-3.ext`` ….

    Guarantees a write never clobbers an existing file.
    """
    p = Path(path)
    if not p.exists():
        return p
    stem, suffix = p.stem, p.suffix
    n = 2
    while True:
        candidate = p.with_name(f"{stem}-{n}{suffix}")
        if not candidate.exists():
            return candidate
        n += 1


# --- atomic writes ---------------------------------------------------------
def write_text(path: os.PathLike[str] | str, text: str) -> Path:
    """Write text atomically, never overwriting (adds ``-N`` suffix if taken)."""
    target = unique_path(path)
    ensure_dir(target.parent)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, target)
    return target


def write_json(path: os.PathLike[str] | str, obj: Any) -> Path:
    """Write pretty JSON atomically, never overwriting. Returns actual path."""
    return write_text(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def append_jsonl(path: os.PathLike[str] | str, obj: Any) -> Path:
    """Append one JSON object as a line; flushed to disk immediately."""
    p = Path(path)
    ensure_dir(p.parent)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return p


def append_csv_row(
    path: os.PathLike[str] | str,
    header: Iterable[str],
    row: Iterable[Any],
) -> Path:
    """Append a CSV row, creating the file with ``header`` if absent."""
    p = Path(path)
    ensure_dir(p.parent)
    new_file = not p.exists()
    with p.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        if new_file:
            writer.writerow(list(header))
        writer.writerow(list(row))
        fh.flush()
        os.fsync(fh.fileno())
    return p


# --- misc ------------------------------------------------------------------
def to_float(value: Any) -> float | None:
    """Parse money-ish strings like ``"1,018.31"`` → ``1018.31``; None on failure."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None
