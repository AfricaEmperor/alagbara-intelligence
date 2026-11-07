import pytest
from zoneinfo import ZoneInfo

from radar_contracts.markets import get_market, market_ids


def test_both_launch_markets_are_explicit_and_timezone_valid():
    assert set(market_ids()) == {"cotonou", "lagos"}
    cot = get_market("cotonou")
    lag = get_market("lagos")
    assert (cot.city, cot.country_code, cot.timezone) == (
        "Cotonou", "BJ", "Africa/Porto-Novo"
    )
    assert (lag.city, lag.country_code, lag.timezone) == (
        "Lagos", "NG", "Africa/Lagos"
    )
    assert ZoneInfo(cot.timezone).key == cot.timezone
    assert ZoneInfo(lag.timezone).key == lag.timezone


def test_market_lookup_is_case_insensitive_but_never_guesses():
    assert get_market("LAGOS").market_id == "lagos"
    with pytest.raises(ValueError, match="unsupported or missing market_id"):
        get_market("")
    with pytest.raises(ValueError, match="unsupported or missing market_id"):
        get_market("Abuja")


def test_market_districts_are_not_cross_assigned():
    cot = {x.casefold() for x in get_market("cotonou").districts}
    lag = {x.casefold() for x in get_market("lagos").districts}
    assert "haie vive" in cot and "haie vive" not in lag
    assert "victoria island" in lag and "victoria island" not in cot
