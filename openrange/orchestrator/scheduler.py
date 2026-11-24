"""Live scheduler: runs the jobs at real market times (US/Eastern, weekdays) with APScheduler.

    python -m openrange.orchestrator.scheduler --role both       one process runs both agents (laptop)
    python -m openrange.orchestrator.scheduler --role analyst    Agent37 sandbox #1
    python -m openrange.orchestrator.scheduler --role trader     Agent37 sandbox #2

With --role analyst / trader each agent runs in its own process (and its own Agent37 sandbox).
They then talk only through BAND (platform.bus: band), exactly like the architecture diagram.

In fake/backtest mode, days are played by jobs.run_day instead (no waiting).
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from openrange.core.config import load_settings
from openrange.core.log import get_logger
from openrange.orchestrator import jobs
from openrange.orchestrator.wiring import TradingSystem, build_system

log = get_logger(__name__)

WATCHLIST_WAIT_TRIES = 12          # trader in its own sandbox: wait up to 12 x 15 s for the Analyst's watchlist
WATCHLIST_WAIT_SECONDS = 15


def trader_open_with_wait(system: TradingSystem, now: datetime) -> None:
    for _ in range(WATCHLIST_WAIT_TRIES):
        jobs.trader_open_job(system, now)
        if system.trader.watchlist is not None:
            return
        time.sleep(WATCHLIST_WAIT_SECONDS)
    log.warning("No watchlist arrived from the Analyst: no trading today")


def jobs_for(role: str) -> dict:
    """Which jobs each process runs. Times come from config/market_us.yaml."""
    analyst = {"weekly": jobs.weekly_job, "premarket": jobs.premarket_job, "open": jobs.analyst_open_job}
    trader = {"open": trader_open_with_wait, "intraday": jobs.intraday_job,
              "close": jobs.close_job, "review": jobs.review_job}
    if role == "analyst":
        return analyst
    if role == "trader":
        return trader
    return {**analyst, **trader, "open": jobs.open_job}


def _guarded(job, system: TradingSystem, name: str, window: tuple[str, str] | None = None):
    """Wrap a job so one failure is logged and never kills the scheduler.
    `window` = ("09:40", "15:50"): skip runs outside it (the 5-min cron covers whole hours)."""
    tz = ZoneInfo(system.settings.market.timezone)

    def run():
        now = datetime.now(tz)
        if window and not (window[0] <= now.strftime("%H:%M") <= window[1]):
            return
        try:
            job(system, now)
        except Exception:
            log.exception("Job %s failed", name)
    return run


def _trigger(name: str, schedule: dict[str, str], tz: str, bar_minutes: int) -> CronTrigger:
    if name == "weekly":                                          # "Sun 18:00"
        day, hhmm = schedule["weekly"].split()
        hour, minute = (int(x) for x in hhmm.split(":"))
        return CronTrigger(day_of_week=day.lower(), hour=hour, minute=minute, timezone=tz)
    if name == "intraday":                                        # every 5 min in the trading hours
        start, end = int(schedule["intraday_start"][:2]), int(schedule["intraday_end"][:2])
        return CronTrigger(day_of_week="mon-fri", hour=f"{start}-{end}", minute=f"*/{bar_minutes}", timezone=tz)
    hour, minute = (int(x) for x in schedule[name].split(":"))
    return CronTrigger(day_of_week="mon-fri", hour=hour, minute=minute, timezone=tz)


def start_live(role: str) -> None:
    settings = load_settings()
    system = build_system(settings)
    m = settings.market
    sched = BlockingScheduler(timezone=m.timezone)
    window = (m.schedule["intraday_start"], m.schedule["intraday_end"])
    for name, job in jobs_for(role).items():
        guarded = _guarded(job, system, name, window if name == "intraday" else None)
        sched.add_job(guarded, _trigger(name, m.schedule, m.timezone, m.session.bar_minutes), name=name)
    log.info("Live scheduler started: role=%s, jobs=%s (%s). Ctrl+C to stop.", role, list(jobs_for(role)), m.timezone)
    sched.start()


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenRange live scheduler")
    parser.add_argument("--role", choices=["both", "analyst", "trader"], default="both")
    start_live(parser.parse_args().role)


if __name__ == "__main__":
    main()
