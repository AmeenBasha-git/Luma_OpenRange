"""T1 signal, T2 gate, T4 broker fills and T5 trade math on hand-made bars."""

from datetime import datetime, timedelta

from openrange.agents.trader import t1_signals, t2_gate, t5_monitor
from openrange.agents.trader.t4_broker import SimBroker
from openrange.core.config import CostSettings
from openrange.core.schemas import Bar, OrderIntent, Pick

COSTS = CostSettings(commission_per_share=0.0035, slippage_per_share=0.01)
T0 = datetime(2026, 11, 20, 9, 35)


def pick(**kw) -> Pick:
    base = dict(ticker="AAA", sector="tech", bias="LONG", conviction=0.5, rvol=2.0, above_ema200=True,
                atr14=4.0, or_high=101.0, or_low=99.0, or_candle="GREEN", reason="t")
    base.update(kw)
    return Pick(**base)


def bar(minute: int, o, h, low, c) -> Bar:
    return Bar(symbol="AAA", ts=T0 + timedelta(minutes=minute), open=o, high=h, low=low, close=c, volume=1000)


def test_long_signal_uses_or_high_and_10pct_atr_stop():
    s = t1_signals.orb_signal(pick(), 0.10, T0)
    assert (s.entry_price, s.stop_price) == (101.0, 100.6)


def test_short_signal_uses_or_low():
    s = t1_signals.orb_signal(pick(bias="SHORT", or_candle="RED", above_ema200=False), 0.10, T0)
    assert (s.entry_price, s.stop_price) == (99.0, 99.4)


def test_gate_blocks_long_below_200ema_and_wrong_candle():
    p = pick(above_ema200=False, or_candle="RED")
    d = t2_gate.check(t1_signals.orb_signal(p, 0.1, T0), p, min_rvol=1.0)
    assert not d.passed
    assert set(d.failed_rules) == {"candle_matches", "trend_matches"}


def test_gate_passes_good_long():
    p = pick()
    assert t2_gate.check(t1_signals.orb_signal(p, 0.1, T0), p, min_rvol=1.0).passed


def intent(qty=100) -> OrderIntent:
    return OrderIntent(ticker="AAA", sector="tech", side="LONG", qty=qty, entry_price=101.0, stop_price=100.6,
                       reason="t")


def test_entry_fills_when_price_reaches_stop_order():
    broker = SimBroker(100_000, COSTS)
    broker.submit(intent(), T0)
    assert broker.on_bar(bar(5, 100.5, 100.9, 100.4, 100.8)) == []          # not reached yet
    fills = broker.on_bar(bar(10, 100.9, 101.5, 100.8, 101.4))
    assert len(fills) == 1 and fills[0].price == 101.01                       # entry + slippage
    assert broker.positions()[0].qty == 100


def test_stop_loss_closes_position_and_trade_is_about_minus_1r():
    broker = SimBroker(100_000, COSTS)
    broker.submit(intent(), T0)
    broker.on_bar(bar(5, 100.9, 101.5, 100.8, 101.4))
    fills = broker.on_bar(bar(10, 101.0, 101.1, 100.0, 100.2))               # falls through the stop
    assert fills[-1].exit_reason == "STOP"
    (position, exit_fill), = broker.pop_closed()
    trade = t5_monitor.to_trade(position, exit_fill, "BULL", COSTS)
    assert -1.2 < trade.r_multiple < -1.0                                     # -1R plus costs
    assert broker.positions() == []


def test_flatten_closes_everything_and_cancels_orders():
    broker = SimBroker(100_000, COSTS)
    broker.submit(intent(), T0)
    broker.on_bar(bar(5, 100.9, 101.5, 100.8, 101.4))
    broker.submit(intent().model_copy(update={"ticker": "BBB"}), T0)
    fills = t5_monitor.flatten(broker, {"AAA": 102.0}, T0 + timedelta(hours=6))
    assert len(fills) == 1 and fills[0].exit_reason == "EOD_FLATTEN"
    assert broker.positions() == [] and broker.open_orders() == []


def test_cash_returns_to_start_minus_costs_on_flat_trade():
    broker = SimBroker(100_000, COSTS)
    broker.submit(intent(), T0)
    broker.on_bar(bar(5, 100.9, 101.5, 100.8, 101.4))
    t5_monitor.flatten(broker, {"AAA": 101.0}, T0 + timedelta(hours=6))
    expected_costs = 100 * (2 * 0.0035 + 2 * 0.01)
    assert abs(broker.cash - (100_000 - expected_costs)) < 1e-6


def test_same_bar_stop_counts_only_after_entry_on_red_bar():
    broker = SimBroker(100_000, COSTS)
    broker.submit(intent(), T0)
    fills = broker.on_bar(bar(5, 100.9, 101.2, 100.3, 100.5))    # red: up to 101.2 (entry), then down to 100.3
    assert [f.purpose for f in fills] == ["ENTRY", "EXIT"]
    assert fills[1].exit_reason == "STOP"


def test_low_before_entry_on_green_bar_does_not_stop_out():
    broker = SimBroker(100_000, COSTS)
    broker.submit(intent(), T0)
    fills = broker.on_bar(bar(5, 100.9, 101.5, 100.3, 101.4))    # green: low 100.3 comes BEFORE the entry
    assert [f.purpose for f in fills] == ["ENTRY"]
    assert broker.positions()[0].ticker == "AAA"
