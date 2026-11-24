"""T5 Monitor. Watches the open book and closes trades.

  - Turns every closed position into a Trade record (P&L net of costs, R multiple).
  - Daily loss stop: once hit, cancel all waiting entry orders (no new trades today).
  - 15:55: cancel waiting orders and close every position at the last price ("flatten").
Stops themselves are held by the broker (like a real bracket order), see t4_broker.py.
"""

from __future__ import annotations

from datetime import datetime

from openrange.agents.trader.t4_broker import Broker
from openrange.core.config import CostSettings
from openrange.core.schemas import Fill, Position, RegimeLabel, Trade


def to_trade(position: Position, exit_fill: Fill, regime: RegimeLabel, costs: CostSettings) -> Trade:
    """P&L uses the slipped fill prices, minus commission on both sides."""
    direction = 1 if position.side == "LONG" else -1
    commissions = 2 * position.qty * costs.commission_per_share
    pnl = direction * (exit_fill.price - position.entry_price) * position.qty - commissions
    initial_risk = position.initial_risk_per_share * position.qty
    return Trade(
        ticker=position.ticker, side=position.side, qty=position.qty,
        entry_price=position.entry_price, exit_price=exit_fill.price,
        pnl=round(pnl, 2), r_multiple=round(pnl / initial_risk, 3),
        costs=round(position.entry_costs + exit_fill.costs, 2), regime=regime,
        exit_reason=exit_fill.exit_reason or "MANUAL", opened=position.opened, closed=exit_fill.ts,
    )


def flatten(broker: Broker, last_prices: dict[str, float], ts: datetime) -> list[Fill]:
    broker.cancel_open_orders()
    return [broker.close_position(p.ticker, last_prices.get(p.ticker, p.entry_price), ts, "EOD_FLATTEN")
            for p in broker.positions()]
