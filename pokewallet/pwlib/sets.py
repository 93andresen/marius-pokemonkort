"""Set-index helpers: load cached ``/sets`` payloads, normalise names, look up.

Shared by ``sync_sets.py`` (produce the index) and ``resolve_portfolio.py``
(consume it). Everything is offline/deterministic — no API calls here.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

from . import config


# --- loading ---------------------------------------------------------------
def raw_sets_files() -> list[Path]:
    directory = config.RAW_DIR / "sets"
    if not directory.exists():
        return []
    return sorted(directory.glob("*__sets.json"))


def latest_raw_sets() -> Path | None:
    files = raw_sets_files()
    return files[-1] if files else None


def load_sets_payload(path: Path | None = None) -> list[dict]:
    """Return the list of set dicts from a cached ``/sets`` capture."""
    path = path or latest_raw_sets()
    if path is None:
        raise FileNotFoundError(
            "No cached /sets capture found. Run "
            "`uv run pokewallet/pokewallet_client.py sets` first."
        )
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        sets = data.get("data") or data.get("sets") or []
    else:
        sets = data
    return [s for s in sets if isinstance(s, dict)]


# --- normalisation ---------------------------------------------------------
def normalize_name(name: Any) -> str:
    """Aggressively normalise a set name for matching.

    Lower-cases, strips accents, maps ``&``→``and``, drops punctuation, and
    collapses whitespace. Intended to line up Collectr names with API names
    despite minor differences.
    """
    if name is None:
        return ""
    text = str(name)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("&", " and ")
    # keep only alphanumerics and spaces
    text = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text)
    return " ".join(text.split())


# --- index -----------------------------------------------------------------
def build_index(sets: list[dict]) -> dict[str, Any]:
    """Build lookup dictionaries keyed by normalised name and by set code."""
    by_name: dict[str, dict] = {}
    by_code: dict[str, dict] = {}
    for item in sets:
        entry = {
            "name": item.get("name"),
            "set_code": item.get("set_code"),
            "set_id": item.get("set_id"),
            "language": item.get("language"),
            "card_count": item.get("card_count"),
            "release_date": item.get("release_date"),
        }
        norm = normalize_name(entry["name"])
        if norm and norm not in by_name:
            by_name[norm] = entry
        code = (entry["set_code"] or "").strip().lower()
        if code and code not in by_code:
            by_code[code] = entry
    return {"by_name": by_name, "by_code": by_code, "count": len(sets)}


def lookup(index: dict[str, Any], name: str | None, code: str | None = None) -> tuple[dict | None, str]:
    """Return ``(entry, method)``. ``method`` is one of:
    ``code`` | ``name_exact`` | ``name_prefix`` | ``none``.
    """
    by_name = index.get("by_name", {})
    by_code = index.get("by_code", {})
    if code:
        hit = by_code.get(str(code).strip().lower())
        if hit:
            return hit, "code"
    norm = normalize_name(name)
    if norm:
        if norm in by_name:
            return by_name[norm], "name_exact"
        # Prefix match: "base set" -> "base set 2" style near-misses.
        candidates = [k for k in by_name if k.startswith(norm) or norm.startswith(k)]
        if len(candidates) == 1:
            return by_name[candidates[0]], "name_prefix"
    return None, "none"
