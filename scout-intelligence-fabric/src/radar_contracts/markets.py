"""Explicit market registry for AP-001 Radar.

This is configuration only: callers must pass a Market explicitly before ingesting
or exporting market-scoped records. No implicit city inference is permitted.
"""
from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class Market:
    market_id: str
    city: str
    country_code: str
    timezone: str
    districts: tuple[str, ...]


MARKETS: dict[str, Market] = {
    "cotonou": Market(
        market_id="cotonou",
        city="Cotonou",
        country_code="BJ",
        timezone="Africa/Porto-Novo",
        districts=(
            "Haie Vive", "Fidjrosse", "Akpakpa", "Cadjehoun", "Ganhi",
            "Zogbo", "Gbegamey", "Jonquet", "Sainte Rita", "Agla",
            "Menontin", "Godomey", "Calavi", "Placodji", "Vodje",
        ),
    ),
    "lagos": Market(
        market_id="lagos",
        city="Lagos",
        country_code="NG",
        timezone="Africa/Lagos",
        districts=(
            "Victoria Island", "Ikoyi", "Lekki", "Lekki Phase 1",
            "Oniru", "Ikate", "Ajah", "Ikeja", "Yaba", "Surulere",
            "VI", "Banana Island", "Eko Atlantic",
        ),
    ),
}


def get_market(market_id: str) -> Market:
    """Return a configured market; fail closed for missing or unknown IDs."""
    key = (market_id or "").strip().lower()
    try:
        market = MARKETS[key]
    except KeyError:
        raise ValueError(f"unsupported or missing market_id: {market_id!r}") from None
    try:
        ZoneInfo(market.timezone)
    except ZoneInfoNotFoundError as exc:  # defensive: fail before processing timestamps
        raise RuntimeError(f"invalid IANA timezone for {key}: {market.timezone}") from exc
    return market


def market_ids() -> tuple[str, ...]:
    return tuple(MARKETS)
