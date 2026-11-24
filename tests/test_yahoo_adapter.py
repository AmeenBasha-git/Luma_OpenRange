"""Yahoo adapter reads saved files correctly: complete days only, no look-ahead, fair RVOL history."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from openrange.data import yahoo

TZ = ZoneInfo("America/New_York")
DAYS = [date(2026, 11, d) for d in (16, 17, 18, 19, 20)]


def five_minute_day(day: date, n_bars: int = 78, first_volume: int = 1000) -> pd.DataFrame:
    start = datetime.combine(day, datetime.min.time(), tzinfo=TZ) + timedelta(hours=9, minutes=30)
    index = [start + timedelta(minutes=5 * i) for i in range(n_bars)]
    volume = [first_volume] + [100] * (n_bars - 1)
    return pd.DataFrame({"open": 10.0, "high": 10.5, "low": 9.5, "close": 10.2, "volume": volume}, index=index)


@pytest.fixture
def cache(tmp_path):
    intraday = pd.concat([five_minute_day(d, first_volume=1000 * (i + 1)) for i, d in enumerate(DAYS[:-1])]
                         + [five_minute_day(DAYS[-1], n_bars=40)])          # last day is incomplete
    intraday.to_pickle(tmp_path / "AAA_5m.pkl")
    intraday.to_pickle(tmp_path / "SPY_5m.pkl")
    daily = pd.DataFrame({"open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 50_000}, index=DAYS)
    daily.to_pickle(tmp_path / "AAA_1d.pkl")
    return tmp_path


def test_incomplete_days_are_skipped(cache):
    assert yahoo.YahooPriceAdapter(cache).trading_days(date(2026, 11, 1), 10) == DAYS[:-1]


def test_intraday_returns_only_finished_bars(cache):
    as_of = datetime(2026, 11, 18, 9, 44, tzinfo=TZ)     # 09:40 bar ends 09:45: not finished yet
    bars = yahoo.YahooPriceAdapter(cache).intraday_bars("AAA", as_of)
    assert [b.ts.strftime("%H:%M") for b in bars] == ["09:30", "09:35"]


def test_daily_excludes_today_until_the_close(cache):
    adapter = yahoo.YahooPriceAdapter(cache)
    morning = datetime(2026, 11, 18, 10, 0, tzinfo=TZ)
    assert adapter.daily_bars("AAA", morning, 10)[-1].ts.date() == date(2026, 11, 17)
    evening = morning.replace(hour=16, minute=30)
    assert adapter.daily_bars("AAA", evening, 10)[-1].ts.date() == date(2026, 11, 18)


def test_opening_volumes_need_full_history(cache):
    adapter = yahoo.YahooPriceAdapter(cache)
    as_of = datetime(2026, 11, 19, 9, 40, tzinfo=TZ)
    assert adapter.opening_volumes("AAA", as_of, 3) == [1000, 2000, 3000]
    assert adapter.opening_volumes("AAA", as_of, 14) == []        # not enough days -> no RVOL


# ------------------------------------------------------------------ Alpaca: 1-minute bars

def test_one_minute_bars_build_correct_five_minute_bars():
    from openrange.data.alpaca import to_five_minutes

    start = datetime(2026, 11, 18, 9, 30, tzinfo=TZ)
    minutes = pd.DataFrame({"open": [10, 11, 12, 13, 14, 20], "high": [11, 12, 15, 14, 15, 21],
                            "low": [9, 10, 11, 12, 13, 19], "close": [11, 12, 13, 14, 15, 20],
                            "volume": [100, 100, 100, 100, 100, 50]},
                           index=[start + timedelta(minutes=i) for i in range(6)])
    five = to_five_minutes(minutes)
    first = five.iloc[0]
    assert (first.open, first.high, first.low, first.close, first.volume) == (10, 15, 9, 15, 500)
    assert five.index[1] == start + timedelta(minutes=5)


def test_execution_bars_use_one_minute_when_available(tmp_path):
    day = DAYS[0]
    start = datetime.combine(day, datetime.min.time(), tzinfo=TZ) + timedelta(hours=9, minutes=30)
    one_minute = pd.DataFrame({"open": 10.0, "high": 10.5, "low": 9.5, "close": 10.2, "volume": 10},
                              index=[start + timedelta(minutes=i) for i in range(390)])
    one_minute.to_pickle(tmp_path / "AAA_1m.pkl")
    five_minute_day(day).to_pickle(tmp_path / "AAA_5m.pkl")
    adapter = yahoo.CachedPriceAdapter(tmp_path, "test")
    as_of = start + timedelta(minutes=12)
    assert len(adapter.execution_bars("AAA", as_of)) == 12          # 1-minute bars
    assert len(adapter.intraday_bars("AAA", as_of)) == 2            # 5-minute bars (strategy view)
