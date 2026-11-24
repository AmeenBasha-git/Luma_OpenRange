"""T3 risk manager enforces every hard limit."""

from datetime import datetime

import pytest

from openrange.agents.trader import t3_risk
from openrange.core.config import load_settings
from openrange.core.schemas import Pick, Signal

RISK = load_settings().risk
TS = datetime(2026, 11, 20, 9, 35)


def make(entry=100.0, stop=99.0, sector="tech"):
    signal = Signal(ticker="AAA", side="LONG", entry_price=entry, stop_price=stop, ts=TS)
    pick = Pick(ticker="AAA", sector=sector, bias="LONG", conviction=0.5, rvol=2.0, above_ema200=True, atr14=10,
                or_high=entry, or_low=entry - 1, or_candle="GREEN", reason="t")
    return signal, pick


def book(equity=100_000.0, start=100_000.0, exposure=0.0, count=0, sectors=None):
    return t3_risk.Book(equity, start, exposure, count, sectors or {})


def test_size_risks_exactly_the_configured_percent():
    signal, pick = make(entry=100, stop=95)            # $5 risk per share: small enough to stay under the cap
    d = t3_risk.size_and_check(signal, pick, book(), RISK, size_mult=1.0)
    assert d.approved
    assert d.intent.qty == int(100_000 * RISK.risk_per_trade_pct / 100 / 5)   # 0.5% of 100k / $5 = 100


def test_half_size_multiplier_halves_quantity():
    signal, pick = make(entry=100, stop=95)
    full = t3_risk.size_and_check(signal, pick, book(), RISK, 1.0).intent.qty
    half = t3_risk.size_and_check(signal, pick, book(), RISK, 0.5).intent.qty
    assert half == full // 2


def test_rejects_after_daily_loss_stop():
    signal, pick = make()
    loss_equity = 100_000 * (1 - RISK.daily_loss_stop_pct / 100)
    d = t3_risk.size_and_check(signal, pick, book(equity=loss_equity), RISK, 1.0)
    assert not d.approved and "daily loss" in d.reason


def test_rejects_when_max_positions_reached():
    signal, pick = make()
    d = t3_risk.size_and_check(signal, pick, book(count=RISK.max_positions), RISK, 1.0)
    assert not d.approved and "positions" in d.reason


def test_rejects_when_sector_is_full():
    signal, pick = make(sector="tech")
    d = t3_risk.size_and_check(signal, pick, book(sectors={"tech": RISK.max_per_sector}), RISK, 1.0)
    assert not d.approved and "sector" in d.reason


def test_per_position_cap_cuts_quantity():
    signal, pick = make(entry=100, stop=99.99)          # tiny stop -> huge risk-based size
    d = t3_risk.size_and_check(signal, pick, book(), RISK, 1.0)
    assert d.approved
    assert d.intent.qty * 100 <= RISK.max_leverage * 100_000 / RISK.max_positions


def test_all_positions_fit_under_leverage():
    """Max positions at the per-position cap must never exceed total leverage."""
    signal, pick = make(entry=100, stop=99.99)
    d = t3_risk.size_and_check(signal, pick, book(), RISK, 1.0)
    assert d.intent.qty * 100 * RISK.max_positions <= RISK.max_leverage * 100_000


@pytest.mark.parametrize("exposure", [RISK.max_leverage * 100_000])
def test_rejects_when_no_leverage_room_left(exposure):
    signal, pick = make()
    d = t3_risk.size_and_check(signal, pick, book(exposure=exposure), RISK, 1.0)
    assert not d.approved
