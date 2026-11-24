"""M6 Direction & Rank (09:35). Builds the final watchlist for the Trader.

For each stock in play:
  direction  = first-candle colour (GREEN -> LONG, RED -> SHORT, DOJI -> skip)   [rulebook 5A]
  conviction = how many other signals agree (fundamentals, sentiment, macro, 200 EMA)
  exclude    = sentiment strongly against the direction, or a hype warning
Rank: highest RVOL first, keep the top `max_picks` (20). The LLM writes the reason for each pick.
"""

from __future__ import annotations

from datetime import datetime

from openrange.core.indicators import atr, ema
from openrange.core.llm import LLMClient, LLMError
from openrange.core.schemas import (
    FundamentalScore,
    InPlay,
    MacroSnapshot,
    Pick,
    PickReason,
    RegimeState,
    SentimentScore,
    Watchlist,
)
from openrange.data.hub import DataHub

SENTIMENT_VETO_LONG = 2.0     # sentiment score <= 2 blocks a LONG
SENTIMENT_VETO_SHORT = 8.0    # sentiment score >= 8 blocks a SHORT
MIN_HISTORY_DAYS = 200        # needed for the 200-day EMA


def conviction(side: str, fundamental: FundamentalScore | None, sentiment: SentimentScore | None,
               macro: MacroSnapshot, above_ema200: bool) -> float:
    """0..1. Each agreeing signal adds its weight."""
    is_long = side == "LONG"
    points = 0.0
    if fundamental:
        points += 0.25 * (fundamental.score if is_long else 1 - fundamental.score)
    if sentiment:
        points += 0.25 * (sentiment.score / 10 if is_long else 1 - sentiment.score / 10)
    if macro.bias == ("RISK_ON" if is_long else "RISK_OFF"):
        points += 0.2
    if above_ema200 == is_long:
        points += 0.3
    return round(points, 3)


def vetoed(side: str, sentiment: SentimentScore | None) -> bool:
    if sentiment is None:
        return False
    if sentiment.hype_warning:
        return True
    return (side == "LONG" and sentiment.score <= SENTIMENT_VETO_LONG) or (
        side == "SHORT" and sentiment.score >= SENTIMENT_VETO_SHORT)


def write_reason(llm: LLMClient, pick: Pick, sentiment: SentimentScore | None, macro: MacroSnapshot) -> str:
    fallback = (f"{pick.bias}: RVOL {pick.rvol:.1f}x, {pick.or_candle.lower()} opening candle, "
                f"{'above' if pick.above_ema200 else 'below'} 200 EMA, macro {macro.bias}.")
    try:
        prompt = (f"In one sentence, explain why {pick.ticker} is a {pick.bias} pick today. Facts only: "
                  f"relative volume {pick.rvol:.1f}x, opening candle {pick.or_candle}, "
                  f"{'above' if pick.above_ema200 else 'below'} its 200-day EMA, "
                  f"sentiment {sentiment.band if sentiment else 'unknown'}, "
                  f"catalyst {pick.catalyst or 'none'}, macro {macro.bias}.")
        return llm.generate(prompt, PickReason, tier="smart").reason
    except LLMError:
        return fallback


def run(in_play: list[InPlay], sectors: dict[str, str], fundamentals: dict[str, FundamentalScore],
        sentiment: dict[str, SentimentScore], macro: MacroSnapshot, regime: RegimeState,
        data: DataHub, llm: LLMClient, as_of: datetime, *, max_picks: int, event_size_mult: float,
        sentiment_veto: bool = True) -> Watchlist:
    picks: list[Pick] = []
    for stock in sorted(in_play, key=lambda s: s.rvol, reverse=True):
        if stock.or_candle == "DOJI":
            continue
        side = "LONG" if stock.or_candle == "GREEN" else "SHORT"
        senti = sentiment.get(stock.symbol)
        if sentiment_veto and vetoed(side, senti):
            continue

        daily = data.prices.daily_bars(stock.symbol, as_of, lookback=260)
        if len(daily) < MIN_HISTORY_DAYS:          # can't judge the 200 EMA trend: skip
            continue
        closes = [b.close for b in daily]
        above = closes[-1] > ema(closes, 200)
        pick = Pick(
            ticker=stock.symbol, sector=sectors.get(stock.symbol, "unknown"), bias=side,
            conviction=conviction(side, fundamentals.get(stock.symbol), senti, macro, above),
            rvol=stock.rvol, above_ema200=above, atr14=round(atr(daily, 14), 4),
            or_high=stock.or_high, or_low=stock.or_low, or_candle=stock.or_candle,
            catalyst=senti.catalyst if senti else None, reason="",
        )
        pick.reason = write_reason(llm, pick, senti, macro)
        picks.append(pick)
        if len(picks) == max_picks:
            break

    size_mult = regime.size_multiplier * (event_size_mult if macro.event_risk_today else 1.0)
    return Watchlist(date=as_of.date(), regime=regime.label, macro_bias=macro.bias,
                     event_risk=macro.event_risk_today, size_multiplier=size_mult, picks=picks)
