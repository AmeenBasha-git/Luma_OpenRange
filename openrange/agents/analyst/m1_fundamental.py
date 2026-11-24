"""M1 Fundamental screen (weekly).

Keeps liquid, quality companies:
  1. Liquidity: price > min_price, 14-day average volume > min_avg_volume, 14-day ATR > min_atr
  2. Quality:   Piotroski F-score >= min_piotroski (9 yes/no checks on the financial statements)
"""

from __future__ import annotations

from datetime import datetime

from openrange.core.indicators import atr
from openrange.core.schemas import FundamentalScore, StockInfo
from openrange.data.fundamentals import Financials
from openrange.data.hub import DataHub


def piotroski_score(f: Financials) -> int:
    """The 9 Piotroski checks. Each true check adds 1 point."""
    checks = [
        f.net_income > 0,                                   # 1 profitable
        f.cash_from_operations > 0,                         # 2 positive operating cash flow
        f.roa > f.roa_prev,                                 # 3 return on assets improving
        f.cash_from_operations > f.net_income,              # 4 earnings backed by cash
        f.long_term_debt_ratio < f.long_term_debt_ratio_prev,  # 5 less leverage
        f.current_ratio > f.current_ratio_prev,             # 6 better liquidity
        f.shares_outstanding <= f.shares_outstanding_prev,  # 7 no new shares issued
        f.gross_margin > f.gross_margin_prev,               # 8 better margin
        f.asset_turnover > f.asset_turnover_prev,           # 9 better efficiency
    ]
    return sum(checks)


def valuation_flag(f: Financials) -> str:
    ratio = f.pe_ratio / f.sector_pe
    if ratio < 0.8:
        return "cheap"
    if ratio > 1.3:
        return "expensive"
    return "fair"


def is_liquid(data: DataHub, symbol: str, as_of: datetime, min_price: float, min_volume: float,
              min_atr: float) -> bool:
    bars = data.prices.daily_bars(symbol, as_of, lookback=15)
    if len(bars) < 15:
        return False
    avg_volume = sum(b.volume for b in bars[-14:]) / 14
    return bars[-1].close > min_price and avg_volume > min_volume and atr(bars, 14) > min_atr


def run(universe: list[StockInfo], data: DataHub, as_of: datetime, *, min_piotroski: int,
        min_price: float, min_avg_volume: float, min_atr: float, use_piotroski: bool = True) -> list[FundamentalScore]:
    """`use_piotroski=False`: only the liquidity filter decides (used while financials are fake)."""
    results = []
    for stock in universe:
        f = data.fundamentals.financials(stock.symbol, as_of)
        score = piotroski_score(f)
        surprise_bonus = 0.1 if (f.earnings_surprise_pct or 0) > 0 else 0.0
        liquid = is_liquid(data, stock.symbol, as_of, min_price, min_avg_volume, min_atr)
        results.append(FundamentalScore(
            symbol=stock.symbol,
            piotroski=score,
            valuation_flag=valuation_flag(f),
            earnings_surprise_pct=f.earnings_surprise_pct,
            score=round(min(1.0, score / 9 * 0.9 + surprise_bonus), 3),
            passed=liquid and (score >= min_piotroski or not use_piotroski),
        ))
    return results
