"""Schemas reject bad data, so a broken module fails loudly instead of passing garbage on."""

from datetime import date

import pytest
from pydantic import ValidationError

from openrange.core.schemas import Pick, Watchlist


def make_pick(**overrides) -> Pick:
    fields = dict(ticker="AAPL", sector="tech", bias="LONG", conviction=0.7, rvol=2.1, above_ema200=True,
                  atr14=3.2, or_high=190.5, or_low=189.0, or_candle="GREEN", reason="test")
    fields.update(overrides)
    return Pick(**fields)


def test_valid_pick_round_trips_through_json():
    pick = make_pick()
    assert Pick.model_validate_json(pick.model_dump_json()) == pick


@pytest.mark.parametrize("bad", [{"bias": "BUY"}, {"conviction": 1.5}, {"atr14": 0}, {"or_candle": "BLUE"}])
def test_pick_rejects_bad_values(bad):
    with pytest.raises(ValidationError):
        make_pick(**bad)


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        make_pick(surprise_field=1)


def test_watchlist_holds_at_most_20_picks():
    picks = [make_pick(ticker=f"T{i}") for i in range(21)]
    with pytest.raises(ValidationError):
        Watchlist(date=date(2026, 11, 20), regime="BULL", macro_bias="RISK_ON", size_multiplier=1.0, picks=picks)

