"""Every message passed between modules is one of these Pydantic models.

Read top to bottom in the order data flows through a trading day:
    market data -> Analyst (M1..M6) -> Watchlist -> Trader (T1..T6) -> DailyReport
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------- shared types

Side = Literal["LONG", "SHORT"]
RegimeLabel = Literal["BULL", "BEAR", "SIDEWAYS", "HIGH_VOL"]
MacroBias = Literal["RISK_ON", "RISK_OFF", "NEUTRAL"]
CandleColor = Literal["GREEN", "RED", "DOJI"]
SentimentBand = Literal[
    "Very Bullish", "Bullish", "Slightly Bullish", "Slightly Bearish", "Bearish", "Very Bearish"
]
Confidence = Literal["low", "medium", "high"]
Tilt = Literal["+", "-", "0"]
ExitReason = Literal["STOP", "EOD_FLATTEN", "MANUAL"]


class Schema(BaseModel):
    """Base for all schemas: no unknown fields allowed."""

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------- market data

class Bar(Schema):
    symbol: str
    ts: datetime                       # bar START time, US/Eastern
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: int = Field(ge=0)


class StockInfo(Schema):
    symbol: str
    sector: str


# ---------------------------------------------------------------- Analyst modules

class FundamentalScore(Schema):                # M1
    symbol: str
    piotroski: int = Field(ge=0, le=9)
    valuation_flag: Literal["cheap", "fair", "expensive"]
    earnings_surprise_pct: float | None = None
    score: float = Field(ge=0, le=1)
    passed: bool


class MacroSnapshot(Schema):                   # M2
    as_of: datetime
    bias: MacroBias
    score: float = Field(ge=-1, le=1)
    drivers: list[str]
    sector_tilt: dict[str, Tilt]
    event_risk_today: str | None = None
    narrative: str


class RegimeState(Schema):                     # M3
    as_of: datetime
    label: RegimeLabel
    confidence: float = Field(ge=0, le=1)
    breadth_pct_above_200ema: float = Field(ge=0, le=100)
    size_multiplier: float = Field(gt=0, le=1)
    explanation: str


class SentimentScore(Schema):                  # M4
    symbol: str
    band: SentimentBand
    score: float = Field(ge=0, le=10)
    confidence: Confidence
    mention_spike: float = Field(ge=0)         # today's mentions / 7-day average
    hype_warning: bool
    catalyst: str | None = None


class InPlay(Schema):                          # M5
    symbol: str
    rvol: float = Field(ge=0)                  # opening-candle volume / 14-day avg of that candle
    gap_pct: float
    or_high: float = Field(gt=0)
    or_low: float = Field(gt=0)
    or_candle: CandleColor


class Pick(Schema):                            # M6 output, one stock
    ticker: str
    sector: str
    bias: Side
    conviction: float = Field(ge=0, le=1)
    rvol: float
    above_ema200: bool
    atr14: float = Field(gt=0)
    or_high: float = Field(gt=0)
    or_low: float = Field(gt=0)
    or_candle: CandleColor
    catalyst: str | None = None
    reason: str


class Watchlist(Schema):                       # Analyst -> Trader hand-off (watchlist.json)
    date: date
    regime: RegimeLabel
    macro_bias: MacroBias
    event_risk: str | None = None
    size_multiplier: float = Field(gt=0, le=1)
    picks: list[Pick] = Field(max_length=20)


# ---------------------------------------------------------------- Trader modules

class Signal(Schema):                          # T1
    ticker: str
    side: Side
    entry_price: float = Field(gt=0)
    stop_price: float = Field(gt=0)
    strategy: str = "ORB5"
    ts: datetime


class GateDecision(Schema):                    # T2
    signal: Signal
    passed: bool
    failed_rules: list[str]


class OrderIntent(Schema):                     # T3 input/output
    ticker: str
    sector: str
    side: Side
    qty: int = Field(gt=0)
    entry_type: Literal["STOP"] = "STOP"
    entry_price: float = Field(gt=0)
    stop_price: float = Field(gt=0)
    reason: str


class RiskDecision(Schema):                    # T3
    intent: OrderIntent | None
    approved: bool
    reason: str


class Order(Schema):                           # T4
    order_id: str
    intent: OrderIntent
    status: Literal["OPEN", "FILLED", "CANCELLED"]
    created: datetime


class Fill(Schema):                            # T4
    order_id: str
    ticker: str
    side: Literal["BUY", "SELL"]
    qty: int = Field(gt=0)
    price: float = Field(gt=0)
    costs: float = Field(ge=0)
    ts: datetime
    purpose: Literal["ENTRY", "EXIT"]
    exit_reason: ExitReason | None = None


class Position(Schema):                        # T4 / T5
    ticker: str
    sector: str
    side: Side
    qty: int = Field(gt=0)
    entry_price: float
    stop_price: float
    initial_risk_per_share: float = Field(gt=0)
    entry_costs: float = Field(ge=0)
    opened: datetime


class Trade(Schema):                           # T5 -> T6
    ticker: str
    side: Side
    qty: int
    entry_price: float
    exit_price: float
    pnl: float                                 # net of costs
    r_multiple: float                          # pnl / initial risk
    costs: float
    regime: RegimeLabel
    exit_reason: ExitReason
    opened: datetime
    closed: datetime


class Lesson(Schema):                          # T6 -> Analyst (next morning)
    date: date
    regime: RegimeLabel
    text: str
    tags: list[str]


class DailyReport(Schema):                     # T6
    date: date
    n_trades: int
    win_rate: float
    avg_r: float
    expectancy: float
    pnl: float
    equity: float
    vs_random_avg_r: float | None = None
    lessons: list[Lesson]


# ---------------------------------------------------------------- LLM structured outputs
# The LLM fills these. If the call fails, the module uses its code-based fallback.

class MacroNarrative(Schema):
    narrative: str


class RegimeExplanation(Schema):
    explanation: str


class SentimentLLMOutput(Schema):
    band: SentimentBand
    score: float = Field(ge=0, le=10)
    confidence: Confidence
    catalyst: str | None = None


class PickReason(Schema):
    reason: str


class LessonsLLMOutput(Schema):
    lessons: list[str]
