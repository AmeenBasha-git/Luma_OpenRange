"""Trade statistics for one run, read straight from the database.

    python -m openrange.backtest.report                 latest backtest run
    python -m openrange.backtest.report <run_id>

R = profit or loss in units of the risk taken (stop distance x shares). +2R = made twice the risk.
Profit factor = total won / total lost. t-stat > 2 = the average is unlikely to be luck.
"""

from __future__ import annotations

import sqlite3
import sys
from statistics import mean, stdev

import pandas as pd

from openrange.core.config import load_settings
from openrange.core.db import read_table


def stats(r_values: list[float]) -> dict[str, float]:
    if not r_values:
        return {"trades": 0}
    wins = [r for r in r_values if r > 0]
    losses = [-r for r in r_values if r <= 0]
    spread = stdev(r_values) if len(r_values) > 1 else 0.0
    return {
        "trades": len(r_values),
        "win_rate": round(len(wins) / len(r_values), 3),
        "avg_r": round(mean(r_values), 3),
        "profit_factor": round(sum(wins) / sum(losses), 2) if losses and sum(losses) else float("inf"),
        "t_stat": round(mean(r_values) / (spread / len(r_values) ** 0.5), 2) if spread else 0.0,
        "best_r": round(max(r_values), 2),
        "worst_r": round(min(r_values), 2),
    }


def latest_run(db_path, mode: str = "backtest") -> str:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT run_id FROM daily_reports WHERE mode = ? ORDER BY id DESC LIMIT 1",
                           (mode,)).fetchone()
    if row is None:
        raise SystemExit(f"No {mode} runs in {db_path}")
    return row[0]


def report(run_id: str | None = None) -> pd.DataFrame:
    db_path = load_settings().db_path
    run_id = run_id or latest_run(db_path)
    trades = read_table(db_path, "trades", run_id)
    if trades.empty:
        raise SystemExit(f"Run {run_id} has no trades")
    rows = {"ALL": stats(trades["r_multiple"].tolist())}
    for column in ("side", "exit_reason"):
        for value, group in trades.groupby(column):
            rows[f"{column}={value}"] = stats(group["r_multiple"].tolist())
    print(f"Run {run_id}: {trades['closed'].str[:10].nunique()} days with trades")
    return pd.DataFrame(rows).T


if __name__ == "__main__":
    with pd.option_context("display.width", 140):
        print(report(sys.argv[1] if len(sys.argv) > 1 else None))
