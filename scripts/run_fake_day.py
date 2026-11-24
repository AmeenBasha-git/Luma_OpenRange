"""Run one full simulated trading day on fake data and print what happened at each step.

    python scripts/run_fake_day.py                 (default day 2026-11-20)
    python scripts/run_fake_day.py 2026-11-18
"""

from __future__ import annotations

import sys
from datetime import date

from openrange.core.config import load_settings
from openrange.orchestrator.jobs import run_day
from openrange.orchestrator.wiring import build_system


def main() -> None:
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2026, 11, 20)
    settings = load_settings()
    system = build_system(settings)
    report = run_day(system, day)
    db = system.db

    count = {t: len(db.load(t)) for t in ("in_play", "signals", "gate_decisions", "orders", "fills", "trades")}
    gate = db.load("gate_decisions")
    watchlist = db.load("watchlists")[-1]

    print("\n" + "=" * 60)
    print(f" OpenRange fake day {day}   run_id={db.run_id}")
    print("=" * 60)
    print(f" Regime / macro      : {watchlist['regime']} / {watchlist['macro_bias']}"
          f"   size x{watchlist['size_multiplier']}")
    print(f" Stocks in play      : {count['in_play']}")
    print(f" Picks (watchlist)   : {len(watchlist['picks'])}")
    print(f" Signals             : {count['signals']}")
    print(f" Gate passed/failed  : {sum(g['passed'] for g in gate)} / {sum(not g['passed'] for g in gate)}")
    print(f" Orders placed       : {count['orders']}")
    print(f" Fills               : {count['fills']}")
    print(f" Trades closed       : {count['trades']}")
    print(f" P&L                 : ${report.pnl:,.2f}   avg {report.avg_r:+.2f}R   win rate {report.win_rate:.0%}")
    print(f" Equity              : ${report.equity:,.2f}")
    print(" Lessons             :")
    for lesson in report.lessons:
        print(f"   - {lesson.text}")
    print("=" * 60)
    db.close()


if __name__ == "__main__":
    main()
