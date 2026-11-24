"""T1 Signal engine: 5-minute Opening Range Breakout (rulebook 5A).

  LONG  entry = buy-stop at the opening-range HIGH;  stop = entry - 10% of the 14-day ATR
  SHORT entry = sell-stop at the opening-range LOW;  stop = entry + 10% of the 14-day ATR
"""

from __future__ import annotations

from datetime import datetime

from openrange.core.schemas import Pick, Signal


def orb_signal(pick: Pick, stop_atr_fraction: float, ts: datetime) -> Signal:
    stop_distance = stop_atr_fraction * pick.atr14
    if pick.bias == "LONG":
        entry, stop = pick.or_high, pick.or_high - stop_distance
    else:
        entry, stop = pick.or_low, pick.or_low + stop_distance
    return Signal(ticker=pick.ticker, side=pick.bias, entry_price=round(entry, 4), stop_price=round(stop, 4),
                  strategy="ORB5", ts=ts)


def run(picks: list[Pick], stop_atr_fraction: float, ts: datetime) -> list[Signal]:
    return [orb_signal(p, stop_atr_fraction, ts) for p in picks]
