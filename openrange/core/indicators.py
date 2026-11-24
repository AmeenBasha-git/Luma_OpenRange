"""Plain indicator math, shared by both agents. Inputs are lists of Bars, oldest first."""

from __future__ import annotations

from openrange.core.schemas import Bar


def ema(values: list[float], period: int) -> float:
    """Exponential moving average of the last value. Needs at least `period` values."""
    if len(values) < period:
        raise ValueError(f"EMA{period} needs {period} values, got {len(values)}")
    k = 2 / (period + 1)
    result = sum(values[:period]) / period          # start from a simple average
    for v in values[period:]:
        result = v * k + result * (1 - k)
    return result


def atr(bars: list[Bar], period: int = 14) -> float:
    """Average True Range over the last `period` bars."""
    if len(bars) < period + 1:
        raise ValueError(f"ATR{period} needs {period + 1} bars, got {len(bars)}")
    true_ranges = [
        max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close))
        for prev, cur in zip(bars[:-1], bars[1:], strict=True)
    ]
    return sum(true_ranges[-period:]) / period


def realized_vol(bars: list[Bar], period: int = 20) -> float:
    """Standard deviation of daily close-to-close returns over `period` days."""
    closes = [b.close for b in bars[-(period + 1):]]
    returns = [b / a - 1 for a, b in zip(closes[:-1], closes[1:], strict=True)]
    mean = sum(returns) / len(returns)
    return (sum((r - mean) ** 2 for r in returns) / len(returns)) ** 0.5


def candle_color(bar: Bar, doji_body_pct: float = 0.10) -> str:
    """GREEN / RED, or DOJI when the body is under 10% of the bar's range."""
    body = abs(bar.close - bar.open)
    if body <= doji_body_pct * (bar.high - bar.low):
        return "DOJI"
    return "GREEN" if bar.close > bar.open else "RED"
