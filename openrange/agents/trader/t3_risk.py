"""T3 Risk manager. Hard-coded limits; nothing (including the LLM) can override them.

Position size:
    risk $   = equity x risk_per_trade_pct% x size multiplier (regime / event day)
    quantity = risk $ / (distance from entry to stop)

Rejects a trade when:
    - the daily loss stop was hit
    - max open positions (including waiting orders) is reached
    - max positions in the same sector is reached
    - the size rounds down to 0 shares
The quantity is also capped so one position is at most  max_leverage x equity / max_positions  in value
(4 x $100k / 20 = $20k). With tight ORB stops the risk-based size alone would be huge, and the first
2-3 orders would use up all the leverage, leaving nothing for the other picks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from openrange.core.config import RiskSettings
from openrange.core.schemas import OrderIntent, Pick, RiskDecision, Signal


@dataclass
class Book:
    """What the account looks like right now (supplied by the broker)."""

    equity: float
    start_of_day_equity: float
    gross_exposure: float          # sum of |qty x price| of open positions AND waiting entry orders
    open_count: int                # open positions + waiting entry orders
    sector_counts: dict[str, int]


def daily_loss_hit(book: Book, risk: RiskSettings) -> bool:
    loss_pct = (book.start_of_day_equity - book.equity) / book.start_of_day_equity * 100
    return loss_pct >= risk.daily_loss_stop_pct


def size_and_check(signal: Signal, pick: Pick, book: Book, risk: RiskSettings, size_mult: float) -> RiskDecision:
    def reject(reason: str) -> RiskDecision:
        return RiskDecision(intent=None, approved=False, reason=reason)

    if daily_loss_hit(book, risk):
        return reject(f"daily loss stop -{risk.daily_loss_stop_pct}% reached")
    if book.open_count >= risk.max_positions:
        return reject(f"max {risk.max_positions} positions reached")
    if book.sector_counts.get(pick.sector, 0) >= risk.max_per_sector:
        return reject(f"max {risk.max_per_sector} positions in sector '{pick.sector}'")

    risk_dollars = book.equity * risk.risk_per_trade_pct / 100 * size_mult
    risk_per_share = abs(signal.entry_price - signal.stop_price)
    qty = math.floor(risk_dollars / risk_per_share)

    reason = f"risk ${risk_dollars:,.0f} / ${risk_per_share:.2f} per share"

    position_cap = risk.max_leverage * book.equity / risk.max_positions
    max_qty_per_position = math.floor(position_cap / signal.entry_price)
    if qty > max_qty_per_position:
        qty = max_qty_per_position
        reason += f"; cut to {qty} shares by ${position_cap:,.0f} per-position cap"

    room = risk.max_leverage * book.equity - book.gross_exposure
    max_qty_by_leverage = math.floor(max(room, 0) / signal.entry_price)
    if qty > max_qty_by_leverage:
        qty = max_qty_by_leverage
        reason += f"; cut to {qty} shares by {risk.max_leverage}x leverage cap"
    if qty < 1:
        return reject("size rounds to 0 shares")

    intent = OrderIntent(ticker=signal.ticker, sector=pick.sector, side=signal.side, qty=qty,
                         entry_price=signal.entry_price, stop_price=signal.stop_price, reason=reason)
    return RiskDecision(intent=intent, approved=True, reason=reason)
