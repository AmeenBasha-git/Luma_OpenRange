"""A whole simulated day runs from 08:00 to 16:15 and every step leaves a record."""

from openrange.core.llm import FakeLLM
from openrange.orchestrator.jobs import run_day
from openrange.orchestrator.wiring import build_system
from tests.conftest import TEST_DAY


def test_full_day_produces_watchlist_orders_and_report(system):
    report = run_day(system, TEST_DAY)
    db = system.db

    assert len(db.load("watchlists")) == 1
    assert len(db.load("signals")) == len(db.load("watchlists")[0]["picks"])
    assert len(db.load("trades")) == report.n_trades
    assert report.lessons, "T6 must always write at least one lesson"
    assert system.broker.positions() == [], "everything must be flat after 15:55"
    assert system.broker.open_orders() == []


def test_lessons_reach_the_analyst_next_morning(system):
    run_day(system, TEST_DAY)
    next_day = TEST_DAY.replace(day=TEST_DAY.day + 3)          # Monday
    run_day(system, next_day)
    assert system.analyst.lessons, "Analyst should have read yesterday's lessons"
    assert system.analyst.lessons[0].date == TEST_DAY


def test_system_still_trades_when_llm_fails(settings):
    system = build_system(settings, llm=FakeLLM(fail=True))
    report = run_day(system, TEST_DAY)
    assert report.lessons and "[fake LLM]" not in report.lessons[0].text     # code fallback was used
    calls = system.db.load("llm_calls")
    assert calls and not any(c["ok"] for c in calls)
    system.db.close()


def test_same_day_gives_same_result(settings):
    first = run_day(build_system(settings, llm=FakeLLM()), TEST_DAY)
    second = run_day(build_system(settings, llm=FakeLLM()), TEST_DAY)
    assert (first.n_trades, first.pnl) == (second.n_trades, second.pnl)
