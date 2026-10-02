"""Set-index helpers: load cached ``/sets`` payloads, normalise names, look up.

Shared by ``sync_sets.py`` (produce the index) and ``resolve_portfolio.py``
(consume it). Everything is offline/deterministic — no API calls here.
"""

from __future__ import annotations

import json
import re
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


# Collectr abbreviations that cannot be scored into the API name directly.
# Keys/values are *normalised* names.
_NAME_ALIASES: dict[str, str] = {
    "sv 151": "sv scarlet and violet 151",
    "151": "sv scarlet and violet 151",
    "pokemon 151": "sv scarlet and violet 151",
    "sword and shield": "swsh base set",
}

# Score band -> method label (drives match confidence downstream).
_METHOD_BY_BAND = [
    (100, "name_exact"),
    (80, "name_suffix"),
    (60, "name_partial"),
    (40, "name_fuzzy"),
]


# Parenthetical language hints Collectr appends, e.g. "Base Set (Japanese)".
_LANG_HINTS: dict[str, str] = {
    "japanese": "jap", "jp": "jap", "jpn": "jap",
    "chinese": "chn", "cn": "chn", "zh": "chn",
    "english": "eng", "en": "eng",
    "korean": "kor", "kr": "kor",
}


def _language_hint(name: str | None) -> str | None:
    match = re.search(r"\(([^)]+)\)", str(name or ""))
    if not match:
        return None
    return _LANG_HINTS.get(match.group(1).strip().lower())


def _strip_parenthetical(name: str | None) -> str:
    return re.sub(r"\([^)]*\)", " ", str(name or "")).strip()


def _contains_seq(hay: list[str], needle: list[str]) -> bool:
    """True if ``needle`` appears as a consecutive token run inside ``hay``."""
    n = len(needle)
    if n == 0 or n > len(hay):
        return False
    return any(hay[i : i + n] == needle for i in range(len(hay) - n + 1))


def _score(cnorm: str, anorm: str) -> float:
    """Score how well a Collectr name (``cnorm``) fits an API name (``anorm``)."""
    ct, at = cnorm.split(), anorm.split()
    if not ct or not at:
        return 0.0
    if ct == at:
        return 100.0
    # API name ends with the Collectr name — the common "CODE: Name" shape.
    if at[-len(ct):] == ct:
        return 80.0 - min(len(at) - len(ct), 20) * 0.5
    # Collectr name appears consecutively inside the API name.
    if _contains_seq(at, ct):
        return 60.0 - min(len(at) - len(ct), 20) * 0.2
    if _contains_seq(ct, at):
        return 45.0
    overlap = len(set(ct) & set(at))
    if overlap:
        return 10.0 + 30.0 * overlap / max(len(ct), len(at))
    return 0.0


def lookup(index: dict[str, Any], name: str | None, code: str | None = None) -> tuple[dict | None, str]:
    """Return ``(entry, method)``.

    ``method`` is one of ``code`` | ``name_exact`` | ``name_suffix`` |
    ``name_partial`` | ``name_fuzzy`` | ``none``.
    """
    by_name = index.get("by_name", {})
    by_code = index.get("by_code", {})
    if code:
        hit = by_code.get(str(code).strip().lower())
        if hit:
            return hit, "code"

    lang = _language_hint(name)
    norm = normalize_name(_strip_parenthetical(name))
    if not norm:
        return None, "none"
    norm = _NAME_ALIASES.get(norm, norm)

    # If the Collectr name declares a language, restrict the search to sets in
    # that language. An unmatched JP card is better than a confidently-wrong
    # match against the English set — and it stays visible as unmatched.
    pool = by_name
    if lang:
        filtered = {
            k: v for k, v in by_name.items()
            if str(v.get("language") or "").lower() == lang
        }
        if filtered:
            pool = filtered

    if norm in pool:
        return pool[norm], "name_exact"

    best_key: tuple[float, int, str] | None = None
    best_norm: str | None = None
    for api_norm, entry in pool.items():
        score = _score(norm, api_norm)
        if score <= 0:
            continue
        # Tie-break: higher score, then shorter (less-prefixed) API name.
        key = (-score, len(api_norm), api_norm)
        if best_key is None or key < best_key:
            best_key = key
            best_norm = api_norm
    if best_key is None or best_norm is None:
        return None, "none"
    score = -best_key[0]
    method = next((label for band, label in _METHOD_BY_BAND if score >= band), "name_fuzzy")
    return pool[best_norm], method
