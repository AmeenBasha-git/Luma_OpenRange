"""Backtest runner: plays N trading days in a row and sums up the results.

    python -m openrange.backtest.runner --start 2026-09-01 --days 20                 (fake prices)
    python -m openrange.backtest.runner --start 2026-09-01 --days 60 --data yahoo    (real prices)
    ... --data yahoo --selection random                                               (baseline: random stocks)

Uses exactly the same Analyst and Trader code as live trading. Only the clock (ReplayClock)
and the broker (SimBroker) differ. 
"""

from __future__ import annotations

import argparse
from datetime import date

from openrange.core.config import load_settings
from openrange.core.schemas import DailyReport
from openrange.orchestrator.jobs import run_day
from openrange.orchestrator.wiring import build_system


def summarize(reports: list[DailyReport], starting_equity: float) -> dict[str, float]:
    n_trades = sum(r.n_trades for r in reports)
    total_r = sum(r.avg_r * r.n_trades for r in reports)
    final_equity = reports[-1].equity if reports else starting_equity
    return {
        "days": len(reports),
        "trades": n_trades,
        "avg_r_per_trade": round(total_r / n_trades, 3) if n_trades else 0.0,
        "total_pnl": round(sum(r.pnl for r in reports), 2),
        "return_pct": round((final_equity / starting_equity - 1) * 100, 2),
        "final_equity": round(final_equity, 2),
    }


def run_backtest(start: date, n_days: int, data: str = "fake", selection: str = "rvol",
                 stop_atr: float | None = None) -> dict[str, float]:
    settings = load_settings(mode="backtest", data=data)
    if stop_atr is not None:
        settings.strategy.stop_atr_fraction = stop_atr
    if selection == "random":
        # Baseline: random stocks instead of Stocks in Play. All other rules stay the same.
        settings.strategy.selection = "random"
        settings.strategy.min_rvol = 0.0
    if data in ("yahoo", "alpaca"):
        # Phase 1: only prices are real. Fake fundamentals/sentiment must not decide anything.
        settings.analyst.filters.piotroski = False
        settings.analyst.filters.sentiment_veto = False
    system = build_system(settings)
    days = system.data.prices.trading_days(start, n_days)
    reports = [run_day(system, day) for day in days]
    summary = {"run_id": system.db.run_id, "selection": selection,
               "stop_atr": settings.strategy.stop_atr_fraction, **summarize(reports, settings.starting_equity)}
    system.db.close()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an OpenRange backtest")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 9, 1))
    parser.add_argument("--days", type=int, default=20)
    parser.add_argument("--data", choices=["fake", "yahoo", "alpaca"], default="fake")
    parser.add_argument("--selection", choices=["rvol", "random"], default="rvol",
                        help="random = baseline: same rules on random stocks")
    parser.add_argument("--stop-atr", type=float, default=None, help="stop distance as a fraction of daily ATR")
    args = parser.parse_args()
    for key, value in run_backtest(args.start, args.days, args.data, args.selection, args.stop_atr).items():
        print(f"{key:>16}: {value}")


if __name__ == "__main__":
    main()
