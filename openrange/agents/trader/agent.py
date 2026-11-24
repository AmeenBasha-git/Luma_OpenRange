"""Trader Agent: decides WHEN and HOW to trade the Analyst's picks, then manages each trade.

Entry points, called by the orchestrator:
    on_open(as_of)    09:35  read watchlist from the bus -> T1 signals -> T2 gate -> T3 risk -> T4 orders
    on_tick(as_of)    every 5 min: new bars -> T4 fills and stops -> T5 trades + daily-loss check
    on_close(as_of)   15:55  T5 flatten everything
    review(as_of)     16:15  T6 report + lessons -> published to the bus for the Analyst
"""

from __future__ import annotations

from datetime import datetime

from openrange.agents.trader import t1_signals, t2_gate, t3_risk, t5_monitor, t6_journal
from openrange.agents.trader.t4_broker import Broker
from openrange.core.config import Settings
from openrange.core.db import Database
from openrange.core.llm import LLMClient
from openrange.core.log import get_logger
from openrange.core.schemas import DailyReport, Trade, Watchlist
from openrange.data.prices import PriceAdapter
from openrange.platform.bus import MessageBus, Topic

log = get_logger(__name__)


class TraderAgent:
    def __init__(self, settings: Settings, prices: PriceAdapter, broker: Broker, llm: LLMClient,
                 db: Database, bus: MessageBus):
        self.settings = settings
        self.prices = prices
        self.broker = broker
        self.llm = llm                       # used ONLY by review() (T6)
        self.db = db
        self.bus = bus
        self._reset_day()

    def _reset_day(self) -> None:
        self.watchlist: Watchlist | None = None
        self.trades: list[Trade] = []
        self.last_prices: dict[str, float] = {}
        self.last_bar_seen: dict[str, datetime] = {}
        self.start_of_day_equity = self.broker.equity({})
        self.stopped_for_day = False

    # ------------------------------------------------------------ 09:35

    def on_open(self, as_of: datetime) -> None:
        self._reset_day()
        message = self.bus.latest(Topic.WATCHLIST)
        if message is None or message["date"] != as_of.date().isoformat():
            log.warning("No watchlist for %s: no trading today", as_of.date())
            return
        self.watchlist = Watchlist.model_validate(message)
        picks = self.watchlist.picks
        s = self.settings

        signals = t1_signals.run(picks, s.strategy.stop_atr_fraction, as_of)
        decisions = t2_gate.run(signals, picks, s.strategy.min_rvol)
        self.db.save_many("signals", signals, as_of, symbol_field="ticker")
        for d in decisions:
            self.db.save("gate_decisions", d, as_of, symbol=d.signal.ticker)

        by_ticker = {p.ticker: p for p in picks}
        submitted = 0
        for decision in (d for d in decisions if d.passed):
            pick = by_ticker[decision.signal.ticker]
            risk = t3_risk.size_and_check(decision.signal, pick, self._book(), s.risk, self.watchlist.size_multiplier)
            self.db.save("risk_decisions", risk, as_of, symbol=pick.ticker)
            if risk.approved and risk.intent:
                order = self.broker.submit(risk.intent, as_of)
                self.db.save("orders", order, as_of, symbol=pick.ticker)
                submitted += 1

        passed = sum(d.passed for d in decisions)
        log.info("09:35 trader: %d picks -> %d passed gate -> %d orders placed", len(picks), passed, submitted)

    # ------------------------------------------------------------ every 5 minutes

    def on_tick(self, as_of: datetime) -> None:
        if self.watchlist is None:
            return
        for pick in self.watchlist.picks:
            for bar in self._new_bars(pick.ticker, as_of):
                self.last_prices[bar.symbol] = bar.close
                for fill in self.broker.on_bar(bar):
                    self.db.save("fills", fill, bar.ts, symbol=fill.ticker)
        self._record_closed()

        equity = self.broker.equity(self.last_prices)
        self.db.save("equity_curve", {"equity": round(equity, 2)}, as_of)
        if not self.stopped_for_day and t3_risk.daily_loss_hit(self._book(), self.settings.risk):
            cancelled = self.broker.cancel_open_orders()
            self.stopped_for_day = True
            log.warning("Daily loss stop hit at %s: %d waiting orders cancelled", as_of.time(), cancelled)

    # ------------------------------------------------------------ 15:55

    def on_close(self, as_of: datetime) -> None:
        self.on_tick(as_of)                                   # process bars up to 15:55 first
        for fill in t5_monitor.flatten(self.broker, self.last_prices, as_of):
            self.db.save("fills", fill, as_of, symbol=fill.ticker)
        self._record_closed()
        self.db.save("equity_curve", {"equity": round(self.broker.equity(self.last_prices), 2)}, as_of)
        log.info("15:55 flatten: %d trades closed today", len(self.trades))

    # ------------------------------------------------------------ 16:15

    def review(self, as_of: datetime) -> DailyReport:
        regime = self.watchlist.regime if self.watchlist else "SIDEWAYS"
        report = t6_journal.run(as_of.date(), self.trades, self.broker.equity(self.last_prices), regime, self.llm)
        self.db.save("daily_reports", report, as_of)
        self.db.save_many("lessons", report.lessons, as_of)
        self.bus.publish(Topic.LESSONS, report, as_of)
        log.info("16:15 review: %d trades, P&L $%.2f, avg %+.2fR", report.n_trades, report.pnl, report.avg_r)
        return report

    # ------------------------------------------------------------ helpers

    def _new_bars(self, ticker: str, as_of: datetime):
        """Finished bars after the opening range (from 09:35) not processed yet.
        These are 1-minute bars when the data source has them, so fills inside a 5-minute bar are exact."""
        seen = self.last_bar_seen.get(ticker)
        or_end = self.settings.market.session.or_end
        bars = [b for b in self.prices.execution_bars(ticker, as_of)
                if b.ts.time() >= or_end and (seen is None or b.ts > seen)]
        if bars:
            self.last_bar_seen[ticker] = bars[-1].ts
        return bars

    def _record_closed(self) -> None:
        regime = self.watchlist.regime if self.watchlist else "SIDEWAYS"
        for position, exit_fill in self.broker.pop_closed():
            trade = t5_monitor.to_trade(position, exit_fill, regime, self.settings.costs)
            self.trades.append(trade)
            self.db.save("trades", trade, exit_fill.ts, symbol=trade.ticker)

    def _book(self) -> t3_risk.Book:
        sector_counts: dict[str, int] = {}
        exposure = 0.0
        for p in self.broker.positions():
            sector_counts[p.sector] = sector_counts.get(p.sector, 0) + 1
            exposure += p.qty * self.last_prices.get(p.ticker, p.entry_price)
        for o in self.broker.open_orders():
            sector_counts[o.intent.sector] = sector_counts.get(o.intent.sector, 0) + 1
            exposure += o.intent.qty * o.intent.entry_price
        return t3_risk.Book(
            equity=self.broker.equity(self.last_prices), start_of_day_equity=self.start_of_day_equity,
            gross_exposure=exposure, open_count=len(self.broker.positions()) + len(self.broker.open_orders()),
            sector_counts=sector_counts,
        )
