"""Price extraction from PokeWallet card objects.

A card may carry ``tcgplayer`` prices, ``cardmarket`` prices, both, or neither.
This module normalises them into a flat dict so downstream code never has to
guess. All values keep their native currency (TCGPlayer = USD, CardMarket = EUR).
"""

from __future__ import annotations

from typing import Any

# Preference order for TCGPlayer sub-types when several exist.
_TCG_SUBTYPE_PREFERENCE = ("normal", "holofoil", "reverse holofoil")

PRICE_FIELDS = [
    "tcg_market", "tcg_low", "tcg_mid", "tcg_high", "tcg_direct_low",
    "tcg_subtype", "tcg_updated",
    "cmk_trend", "cmk_avg", "cmk_low", "cmk_avg1", "cmk_avg7", "cmk_avg30",
    "cmk_variant", "cmk_updated",
    "has_tcg", "has_cmk", "price_source",
]


def _pick_tcg_price(prices: list[dict]) -> dict | None:
    if not prices:
        return None
    for wanted in _TCG_SUBTYPE_PREFERENCE:
        for price in prices:
            if str(price.get("sub_type_name") or "").strip().lower() == wanted:
                return price
    return prices[0]


def extract_prices(card: dict) -> dict:
    """Flatten a PokeWallet card's price sources into a single dict."""
    out: dict[str, Any] = {field: None for field in PRICE_FIELDS}
    out["has_tcg"] = False
    out["has_cmk"] = False

    tcg = card.get("tcgplayer") or {}
    chosen = _pick_tcg_price(list(tcg.get("prices") or []))
    if chosen:
        out["has_tcg"] = True
        out["tcg_market"] = chosen.get("market_price")
        out["tcg_low"] = chosen.get("low_price")
        out["tcg_mid"] = chosen.get("mid_price")
        out["tcg_high"] = chosen.get("high_price")
        out["tcg_direct_low"] = chosen.get("direct_low_price")
        out["tcg_subtype"] = chosen.get("sub_type_name")
        out["tcg_updated"] = chosen.get("updated_at")

    cmk = card.get("cardmarket") or {}
    if cmk:
        out["has_cmk"] = True
        out["cmk_trend"] = cmk.get("trend")
        out["cmk_avg"] = cmk.get("avg")
        out["cmk_low"] = cmk.get("low")
        out["cmk_avg1"] = cmk.get("avg1")
        out["cmk_avg7"] = cmk.get("avg7")
        out["cmk_avg30"] = cmk.get("avg30")
        out["cmk_variant"] = cmk.get("variant_type")
        out["cmk_updated"] = cmk.get("updated_at")

    if out["has_tcg"] and out["has_cmk"]:
        out["price_source"] = "both"
    elif out["has_tcg"]:
        out["price_source"] = "tcgplayer"
    elif out["has_cmk"]:
        out["price_source"] = "cardmarket"
    else:
        out["price_source"] = "none"
    return out


def card_identity(card: dict) -> dict:
    """Extract the identity/metadata fields we care about from a card object."""
    info = card.get("card_info") or card
    return {
        "pk_id": card.get("id"),
        "pk_name": info.get("name"),
        "pk_clean_name": info.get("clean_name"),
        "pk_set_name": info.get("set_name"),
        "pk_set_code": info.get("set_code"),
        "pk_set_id": info.get("set_id"),
        "pk_card_number": info.get("card_number"),
        "pk_rarity": info.get("rarity"),
        "pk_card_type": info.get("card_type"),
        "pk_product_type": info.get("product_type"),
        "tcgplayer_url": (card.get("tcgplayer") or {}).get("url"),
    }
