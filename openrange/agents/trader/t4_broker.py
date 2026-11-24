"""T4 Execution. One Broker interface, two implementations:

    SimBroker          our own simulator (fake days, backtests, default live paper)
    AlpacaPaperBroker  Alpaca paper account (Phase 5)

SimBroker rules:
  - Entry orders are STOP orders. A LONG fills when a bar's high reaches the entry price
    (at the entry price, or the bar's open if it gapped through). SHORT is the mirror image.
  - Each filled position has a protective stop, held by the broker. It fills when a bar touches it.
  - Inside one bar we only know open/high/low/close, so we assume the usual path:
        green bar: open -> low -> high -> close      red bar: open -> high -> low -> close
    The stop only counts if the price reaches it AFTER the entry on that path.
  - Costs per share, each side: commission + slippage (slippage always moves the price against us).
"""

from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from datetime import datetime

from openrange.core.config import CostSettings
from openrange.core.schemas import Bar, ExitReason, Fill, Order, OrderIntent, Position


def bar_path(bar: Bar) -> list[float]:
    """The assumed price path inside one bar."""
    if bar.close >= bar.open:
        return [bar.open, bar.low, bar.high, bar.close]
    return [bar.open, bar.high, bar.low, bar.close]


def first_cross(path: list[float], level: float, upward: bool) -> int | None:
    """Index of the first path point at or beyond `level` (upward: >= level, downward: <= level)."""
    for i, price in enumerate(path):
        if (price >= level) if upward else (price <= level):
            return i
    return None


class Broker(ABC):
    @abstractmethod
    def submit(self, intent: OrderIntent, ts: datetime) -> Order: ...

    @abstractmethod
    def cancel_open_orders(self) -> int:
        """Cancel every waiting entry order. Returns how many were cancelled."""

    @abstractmethod
    def on_bar(self, bar: Bar) -> list[Fill]:
        """Feed one new bar. Returns entry and stop fills it caused."""

    @abstractmethod
    def close_position(self, ticker: str, price: float, ts: datetime, reason: ExitReason) -> Fill: ...

    @abstractmethod
    def positions(self) -> list[Position]: ...

    @abstractmethod
    def open_orders(self) -> list[Order]: ...

    @abstractmethod
    def equity(self, last_prices: dict[str, float]) -> float: ...

    @abstractmethod
    def pop_closed(self) -> list[tuple[Position, Fill]]:
        """Positions closed since the last call, each with its exit fill."""


class SimBroker(Broker):
    def __init__(self, starting_cash: float, costs: CostSettings):
        self.cash = starting_cash
        self.costs = costs
        self._orders: dict[str, Order] = {}
        self._positions: dict[str, Position] = {}
        self._closed: list[tuple[Position, Fill]] = []
        self._ids = itertools.count(1)

    # ------------------------------------------------------------ orders

    def submit(self, intent: OrderIntent, ts: datetime) -> Order:
        order = Order(order_id=f"SIM-{next(self._ids)}", intent=intent, status="OPEN", created=ts)
        self._orders[order.order_id] = order
        return order

    def cancel_open_orders(self) -> int:
        waiting = [o for o in self._orders.values() if o.status == "OPEN"]
        for order in waiting:
            order.status = "CANCELLED"
        return len(waiting)

    def open_orders(self) -> list[Order]:
        return [o for o in self._orders.values() if o.status == "OPEN"]

    def positions(self) -> list[Position]:
        return list(self._positions.values())

    # ------------------------------------------------------------ market events

    def on_bar(self, bar: Bar) -> list[Fill]:
        fills = []
        path = bar_path(bar)
        entry_step = None                     # where on the path today's entry happened (None = earlier bar)
        for order in self.open_orders():
            if order.intent.ticker != bar.symbol:
                continue
            step = first_cross(path, order.intent.entry_price, upward=order.intent.side == "LONG")
            if step is not None:
                fills.append(self._fill_entry(order, bar))
                entry_step = step

        position = self._positions.get(bar.symbol)
        if position:
            after_entry = path if entry_step is None else path[entry_step:]
            is_long = position.side == "LONG"
            if first_cross(after_entry, position.stop_price, upward=not is_long) is not None:
                price = position.stop_price
                if entry_step is None:        # held from an earlier bar: a gap through the stop fills at the open
                    price = min(price, bar.open) if is_long else max(price, bar.open)
                fills.append(self.close_position(bar.symbol, price, bar.ts, "STOP"))
        return fills

    def close_position(self, ticker: str, price: float, ts: datetime, reason: ExitReason) -> Fill:
        position = self._positions.pop(ticker)
        exit_price = self._slipped(price, buying=position.side == "SHORT")
        costs = position.qty * self.costs.commission_per_share
        if position.side == "LONG":
            self.cash += position.qty * exit_price - costs
        else:
            self.cash -= position.qty * exit_price + costs
        fill = Fill(order_id=f"EXIT-{ticker}", ticker=ticker, side="SELL" if position.side == "LONG" else "BUY",
                    qty=position.qty, price=round(exit_price, 4), costs=round(costs + self._slip_cost(position.qty), 4),
                    ts=ts, purpose="EXIT", exit_reason=reason)
        self._closed.append((position, fill))
        return fill

    def pop_closed(self) -> list[tuple[Position, Fill]]:
        closed, self._closed = self._closed, []
        return closed

    def equity(self, last_prices: dict[str, float]) -> float:
        value = self.cash
        for p in self._positions.values():
            price = last_prices.get(p.ticker, p.entry_price)
            value += p.qty * price if p.side == "LONG" else -p.qty * price
        return value

    # ------------------------------------------------------------ internals

    def _fill_entry(self, order: Order, bar: Bar) -> Fill:
        intent = order.intent
        is_long = intent.side == "LONG"
        trigger = max(intent.entry_price, bar.open) if is_long else min(intent.entry_price, bar.open)
        price = self._slipped(trigger, buying=is_long)
        costs = intent.qty * self.costs.commission_per_share
        self.cash += -intent.qty * price - costs if is_long else intent.qty * price - costs
        order.status = "FILLED"

        self._positions[intent.ticker] = Position(
            ticker=intent.ticker, sector=intent.sector, side=intent.side, qty=intent.qty,
            entry_price=round(price, 4), stop_price=intent.stop_price,
            initial_risk_per_share=abs(price - intent.stop_price),
            entry_costs=round(costs + self._slip_cost(intent.qty), 4), opened=bar.ts,
        )
        return Fill(order_id=order.order_id, ticker=intent.ticker, side="BUY" if is_long else "SELL",
                    qty=intent.qty, price=round(price, 4), costs=round(costs + self._slip_cost(intent.qty), 4),
                    ts=bar.ts, purpose="ENTRY")

    def _slipped(self, price: float, buying: bool) -> float:
        return price + self.costs.slippage_per_share if buying else price - self.costs.slippage_per_share

    def _slip_cost(self, qty: int) -> float:
        return qty * self.costs.slippage_per_share


class AlpacaPaperBroker(Broker):
    """Alpaca paper trading. Needs ALPACA_KEY / ALPACA_SECRET. Built in Phase 5."""

    def __init__(self, key: str, secret: str):
        raise NotImplementedError("AlpacaPaperBroker is built in Phase 5. Use broker: sim for now.")

    def submit(self, intent, ts): ...
    def cancel_open_orders(self): ...
    def on_bar(self, bar): ...
    def close_position(self, ticker, price, ts, reason): ...
    def positions(self): ...
    def open_orders(self): ...
    def equity(self, last_prices): ...
    def pop_closed(self): ...
