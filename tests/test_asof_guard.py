"""No adapter may return data from after `as_of` (no look-ahead bias)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from openrange.data.base import LookAheadError, assert_not_after
from openrange.data.hub import fake_data_hub

TZ = ZoneInfo("America/New_York")
AS_OF = datetime(2026, 11, 20, 10, 2, tzinfo=TZ)


def test_intraday_bars_are_only_finished_bars():
    bars = fake_data_hub().prices.intraday_bars("AAPL", AS_OF)
    assert bars, "expected some bars by 10:02"
    assert all(b.ts + timedelta(minutes=5) <= AS_OF for b in bars)
    assert bars[-1].ts == datetime(2026, 11, 20, 9, 55, tzinfo=TZ)     # 09:55-10:00 is the last finished bar


def test_daily_bars_exclude_today_before_the_close():
    bars = fake_data_hub().prices.daily_bars("AAPL", AS_OF, lookback=5)
    assert all(b.ts.date() < AS_OF.date() for b in bars)


def test_daily_bars_include_today_after_the_close():
    after_close = AS_OF.replace(hour=16, minute=30)
    bars = fake_data_hub().prices.daily_bars("AAPL", after_close, lookback=5)
    assert bars[-1].ts.date() == after_close.date()


def test_news_is_never_from_the_future():
    for symbol in ("AAPL", "NVDA", "JPM"):
        assert all(h.ts <= AS_OF for h in fake_data_hub().news.headlines(symbol, AS_OF))


def test_guard_raises_on_future_rows():
    with pytest.raises(LookAheadError):
        assert_not_after([AS_OF + timedelta(minutes=1)], AS_OF, "test")
