"""The trading day as a list of jobs (all times US/Eastern, from config/market_us.yaml):

    weekly     Sun 18:00    Analyst: M1 fundamentals (live scheduler only)
    premarket  08:00        Analyst: macro, regime, sentiment          (weekly M1 runs first if needed)
    open       09:35        Analyst: in play + rank -> watchlist  ->  Trader: orders
    intraday   09:40-15:50  Trader: every 5 minutes
    close      15:55        Trader: flatten
    review     16:15        Trader: report + lessons -> Analyst

`run_day` plays one whole day on a ReplayClock (fake day or backtest day).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from openrange.core.clock import ReplayClock, at
from openrange.core.schemas import DailyReport
from openrange.orchestrator.wiring import TradingSystem


def _hhmm(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def weekly_job(system: TradingSystem, now: datetime) -> None:
    system.analyst.run_weekly(now)


def premarket_job(system: TradingSystem, now: datetime) -> None:
    system.analyst.run_premarket(now)


def analyst_open_job(system: TradingSystem, now: datetime) -> None:
    system.analyst.run_open(now)


def trader_open_job(system: TradingSystem, now: datetime) -> None:
    system.trader.on_open(now)


def open_job(system: TradingSystem, now: datetime) -> None:
    """Both agents in one process: Analyst publishes the watchlist, then the Trader reads it."""
    analyst_open_job(system, now)
    trader_open_job(system, now)


def intraday_job(system: TradingSystem, now: datetime) -> None:
    system.trader.on_tick(now)


def close_job(system: TradingSystem, now: datetime) -> None:
    system.trader.on_close(now)


def review_job(system: TradingSystem, now: datetime) -> DailyReport:
    return system.trader.review(now)


def day_timeline(day: date, schedule: dict[str, str], tz: str, bar_minutes: int) -> list[tuple[datetime, str]]:
    """Every (time, job name) of one trading day, in order."""
    events = [(at(day, _hhmm(schedule["premarket"]), tz), "premarket"),
              (at(day, _hhmm(schedule["open"]), tz), "open")]
    t = at(day, _hhmm(schedule["intraday_start"]), tz)
    end = at(day, _hhmm(schedule["intraday_end"]), tz)
    while t <= end:
        events.append((t, "intraday"))
        t += timedelta(minutes=bar_minutes)
    events.append((at(day, _hhmm(schedule["close"]), tz), "close"))
    events.append((at(day, _hhmm(schedule["review"]), tz), "review"))
    return events


JOBS = {"premarket": premarket_job, "open": open_job, "intraday": intraday_job,
        "close": close_job, "review": review_job}


def run_day(system: TradingSystem, day: date) -> DailyReport:
    m = system.settings.market
    timeline = day_timeline(day, m.schedule, m.timezone, m.session.bar_minutes)
    clock = ReplayClock(timeline[0][0], m.timezone, m.session.open, m.session.close)
    report = None
    for when, job_name in timeline:
        clock.sleep_until(when)
        result = JOBS[job_name](system, clock.now())
        if job_name == "review":
            report = result
    return report
