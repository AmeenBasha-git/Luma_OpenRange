"""M3 Regime (daily, pre-market). Labels the market BULL / BEAR / SIDEWAYS / HIGH_VOL.

Phase 0 uses simple rules on SPY. Phase 2 replaces `classify` with an HMM (hmmlearn);
the output schema stays the same.

The regime only changes position SIZE (High-Vol = half size). It is not an entry filter,
because the backtest showed an SPY filter did not help (PROJECT_SPEC.md Section 5A).
"""

from __future__ import annotations

from datetime import datetime

from openrange.core.indicators import ema, realized_vol
from openrange.core.llm import LLMClient, LLMError
from openrange.core.schemas import Bar, RegimeExplanation, RegimeState, StockInfo
from openrange.data.hub import DataHub

HIGH_VOL_RATIO = 1.5       # 20-day vol above 1.5x its 1-year median = HIGH_VOL


def classify(spy: list[Bar]) -> tuple[str, float, str]:
    """Return (label, confidence, one-line reason) from SPY daily bars (needs 260)."""
    closes = [b.close for b in spy]
    ema200, ema50, ema50_prev = ema(closes, 200), ema(closes, 50), ema(closes[:-10], 50)
    vol_now = realized_vol(spy, 20)
    yearly = sorted(realized_vol(spy[: len(spy) - k], 20) for k in range(0, 250, 10))
    vol_ratio = vol_now / yearly[len(yearly) // 2]
    price = closes[-1]

    if vol_ratio > HIGH_VOL_RATIO:
        return "HIGH_VOL", min(1.0, vol_ratio / 2), f"20-day volatility is {vol_ratio:.1f}x normal"
    distance = (price - ema200) / ema200
    if price > ema200 and ema50 > ema50_prev:
        return "BULL", min(1.0, 0.5 + distance * 5), f"SPY {distance:+.1%} above its 200 EMA, 50 EMA rising"
    if price < ema200 and ema50 < ema50_prev:
        return "BEAR", min(1.0, 0.5 - distance * 5), f"SPY {distance:+.1%} below its 200 EMA, 50 EMA falling"
    return "SIDEWAYS", 0.5, "SPY trend and 50 EMA disagree"


def breadth(universe: list[StockInfo], data: DataHub, as_of: datetime) -> float:
    """% of universe stocks closing above their 200 EMA (stocks with under 200 days of history are skipped)."""
    above = counted = 0
    for stock in universe:
        closes = [b.close for b in data.prices.daily_bars(stock.symbol, as_of, lookback=260)]
        if len(closes) >= 200:
            above += closes[-1] > ema(closes, 200)
            counted += 1
    return round(100 * above / counted, 1) if counted else 50.0


def run(universe: list[StockInfo], data: DataHub, llm: LLMClient, as_of: datetime, *,
        benchmark: str, high_vol_size_mult: float) -> RegimeState:
    spy = data.prices.daily_bars(benchmark, as_of, lookback=260)
    label, confidence, reason = classify(spy)
    pct_above = breadth(universe, data, as_of)

    explanation = f"{reason}; {pct_above:.0f}% of stocks above their 200 EMA."      # code fallback
    try:
        prompt = (f"Explain in 2 plain sentences why the market regime is {label}. "
                  f"Facts: {reason}. Breadth: {pct_above:.0f}% of stocks above 200 EMA. Do not invent numbers.")
        explanation = llm.generate(prompt, RegimeExplanation, tier="smart").explanation
    except LLMError:
        pass

    return RegimeState(
        as_of=as_of, label=label, confidence=round(confidence, 2), breadth_pct_above_200ema=pct_above,
        size_multiplier=high_vol_size_mult if label == "HIGH_VOL" else 1.0, explanation=explanation,
    )
