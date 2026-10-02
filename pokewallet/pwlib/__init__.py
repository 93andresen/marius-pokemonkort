"""pwlib — shared helpers for the marius-pokemonkort PokeWallet tooling.

Import from scripts living in ``pokewallet/`` like::

    from pwlib.api import PokeWalletClient
    from pwlib.config import RAW_DIR

(the script's own directory is on ``sys.path`` when run via ``uv run``).
"""

from . import config  # noqa: F401
from . import util  # noqa: F401

__all__ = ["config", "util"]
