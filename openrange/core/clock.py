"""Clocks. The Trader never calls datetime.now() directly; it asks the clock.

LiveClock   -> real time (live paper trading)
ReplayClock -> a fixed list of timestamps, advanced instantly (fake day, backtest)
"""

from __future__ import annotations

import time as _time
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from datetime import time as dtime
from zoneinfo import ZoneInfo


class Clock(ABC):
    def __init__(self, timezone: str, market_open: dtime, market_close: dtime):
        self.tz = ZoneInfo(timezone)
        self.market_open = market_open
        self.market_close = market_close

    @abstractmethod
    def now(self) -> datetime: ...

    @abstractmethod
    def sleep_until(self, t: datetime) -> None: ...

    def today(self) -> date:
        return self.now().date()

    def is_market_open(self) -> bool:
        now = self.now()
        return now.weekday() < 5 and self.market_open <= now.time() < self.market_close


class LiveClock(Clock):
    def now(self) -> datetime:
        return datetime.now(self.tz)

    def sleep_until(self, t: datetime) -> None:
        seconds = (t - self.now()).total_seconds()
        if seconds > 0:
            _time.sleep(seconds)


class ReplayClock(Clock):
    """Jumps straight to the requested time. Used for fake days and backtests."""

    def __init__(self, start: datetime, timezone: str, market_open: dtime, market_close: dtime):
        super().__init__(timezone, market_open, market_close)
        self._now = start.replace(tzinfo=self.tz) if start.tzinfo is None else start

    def now(self) -> datetime:
        return self._now

    def sleep_until(self, t: datetime) -> None:
        if t < self._now:
            raise ValueError(f"ReplayClock cannot go back in time: {t} < {self._now}")
        self._now = t

    def advance(self, delta: timedelta) -> None:
        self._now = self._now + delta


def at(day: date, hhmm: dtime, tz: str) -> datetime:
    """Build a timezone-aware datetime for a day + time."""
    return datetime.combine(day, hhmm, tzinfo=ZoneInfo(tz))
