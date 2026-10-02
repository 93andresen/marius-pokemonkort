"""Central configuration: paths, IDs, rate-budget thresholds, API base.

Nothing here is secret except the API key, which is only ever read from the
environment (``API_KEY_POKEWALLET``). Never hard-code the key into a file.
"""

from __future__ import annotations

import os
from pathlib import Path


def _repo_root() -> Path:
    """Locate the repo root.

    ``POKEMONKORT_ROOT`` wins if set; otherwise we walk up from this file,
    which lives at ``<repo>/pokewallet/pwlib/config.py`` →
    ``parents[2]`` is the repo root.
    """
    env = os.environ.get("POKEMONKORT_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


REPO_ROOT: Path = _repo_root()

# --- data / logs / state ---------------------------------------------------
DATA_DIR: Path = REPO_ROOT / "data"
LOG_DIR: Path = REPO_ROOT / "logs"
STATE_DIR: Path = REPO_ROOT / "state"

POKEWALLET_DATA: Path = DATA_DIR / "pokewallet"
RAW_DIR: Path = POKEWALLET_DATA / "raw"
SETS_DIR: Path = POKEWALLET_DATA / "sets"
SNAPSHOTS_DIR: Path = POKEWALLET_DATA / "snapshots"

# --- identifiers -----------------------------------------------------------
# Canonical home for the Sheet ID is the top of AGENTS.md; this is the
# documented default and may be overridden by env.
SHEET_ID: str = os.environ.get(
    "POKEMONKORT_SHEET_ID", "13TfMos8hP4zT3-Tf92F7ZE0hJ2r7cKJdEqvdj0gvtpM"
)
APPS_SCRIPT_ID: str = os.environ.get(
    "POKEMONKORT_APPS_SCRIPT_ID",
    "1zuV63oR_FZN1NRxlpgsrx5cFUuPc3p4ZgR2_pEZ8GZvJwvZEj6y2yUtr",
)

# --- PokeWallet API --------------------------------------------------------
BASE_URL: str = os.environ.get("POKEWALLET_BASE_URL", "https://api.pokewallet.io")
API_KEY_ENV: str = "API_KEY_POKEWALLET"

# --- rate budget -----------------------------------------------------------
HOURLY_LIMIT: int = 100
DAILY_LIMIT: int = 1000
# Never spend the last few requests of a window — leave headroom for
# interactive / browser use.
MIN_HOUR_REMAINING_DEFAULT: int = 5
MIN_DAY_REMAINING_DEFAULT: int = 20

# --- collectr export -------------------------------------------------------
COLLECTR_CSV: Path = (
    REPO_ROOT
    / "getcollectr"
    / "marius_pokemon_cards_collectr_export_2026-10-02-052742.csv"
)

RATE_LOG_CSV: Path = LOG_DIR / "ratelog.csv"

ALL_DIRS = [
    DATA_DIR,
    LOG_DIR,
    STATE_DIR,
    POKEWALLET_DATA,
    RAW_DIR,
    SETS_DIR,
    SNAPSHOTS_DIR,
]
