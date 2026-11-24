"""M5 Stocks in Play (09:35, after the first 5-minute candle).

  RVOL = volume of today's 09:30-09:35 candle / average volume of that same candle over the last 14 days
  Keep RVOL >= min_rvol (1.0). This filter is where most of the edge comes from (Zarattini et al. 2024).

selection="random" is the BASELINE: pick random stocks instead (same count, same later rules).
If the strategy does no better on our picks than on random ones, the selection adds nothing.
"""

from __future__ import annotations

import random
from datetime import datetime

from openrange.core.indicators import candle_color
from openrange.core.schemas import InPlay
from openrange.data.hub import DataHub

RVOL_LOOKBACK_DAYS = 14


def measure(symbol: str, data: DataHub, as_of: datetime) -> InPlay | None:
    """RVOL, gap and opening-range numbers for one stock. None if the first candle isn't finished."""
    today = data.prices.intraday_bars(symbol, as_of)
    history = data.prices.opening_volumes(symbol, as_of, RVOL_LOOKBACK_DAYS)
    prev_close = data.prices.daily_bars(symbol, as_of, lookback=1)
    if not today or not history or not prev_close:
        return None

    first = today[0]
    avg_opening_volume = sum(history) / len(history)
    return InPlay(
        symbol=symbol,
        rvol=round(first.volume / avg_opening_volume, 2),
        gap_pct=round((first.open / prev_close[-1].close - 1) * 100, 2),
        or_high=first.high,
        or_low=first.low,
        or_candle=candle_color(first),
    )


def run(symbols: list[str], data: DataHub, as_of: datetime, min_rvol: float,
        selection: str = "rvol", random_count: int = 20) -> list[InPlay]:
    """selection="rvol": stocks with RVOL >= min_rvol, highest first.
    selection="random": `random_count` random stocks (seeded by date, so runs repeat)."""
    measured = [m for m in (measure(s, data, as_of) for s in symbols) if m is not None]
    if selection == "random":
        return random.Random(as_of.date().isoformat()).sample(measured, min(random_count, len(measured)))
    in_play = [m for m in measured if m.rvol >= min_rvol]
    return sorted(in_play, key=lambda m: m.rvol, reverse=True)
