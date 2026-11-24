"""T6 Journal & Lessons (16:15). The only Trader module allowed to use the LLM.

Stats:   number of trades, win rate, average R, expectancy ($ per trade), P&L, equity
Lessons: the LLM reviews the day and writes short lessons, tagged with today's regime.
         If the LLM fails, a code-written summary is used instead.
"""

from __future__ import annotations

from datetime import date

from openrange.core.llm import LLMClient, LLMError
from openrange.core.schemas import DailyReport, Lesson, LessonsLLMOutput, RegimeLabel, Trade


def stats(trades: list[Trade]) -> dict[str, float]:
    if not trades:
        return {"n_trades": 0, "win_rate": 0.0, "avg_r": 0.0, "expectancy": 0.0, "pnl": 0.0}
    wins = [t for t in trades if t.pnl > 0]
    pnl = sum(t.pnl for t in trades)
    return {
        "n_trades": len(trades),
        "win_rate": round(len(wins) / len(trades), 3),
        "avg_r": round(sum(t.r_multiple for t in trades) / len(trades), 3),
        "expectancy": round(pnl / len(trades), 2),
        "pnl": round(pnl, 2),
    }


def fallback_lesson(s: dict[str, float], regime: RegimeLabel) -> str:
    if s["n_trades"] == 0:
        return f"No trades in a {regime} day: no stock passed every rule."
    return (f"{s['n_trades']} trades in a {regime} day: win rate {s['win_rate']:.0%}, "
            f"average {s['avg_r']:+.2f}R. One day is too small a sample to change the rules.")


def run(day: date, trades: list[Trade], equity: float, regime: RegimeLabel, llm: LLMClient) -> DailyReport:
    s = stats(trades)
    texts = [fallback_lesson(s, regime)]
    try:
        summary = [f"{t.ticker} {t.side} {t.r_multiple:+.2f}R ({t.exit_reason})" for t in trades]
        prompt = (f"You review an ORB day-trading system. Regime: {regime}. Stats: {s}. Trades: {summary or 'none'}. "
                  "Write at most 3 short, specific lessons. Do not suggest changing rules after one day.")
        texts = llm.generate(prompt, LessonsLLMOutput, tier="smart").lessons[:3] or texts
    except LLMError:
        pass

    lessons = [Lesson(date=day, regime=regime, text=text, tags=[regime, "ORB5"]) for text in texts]
    return DailyReport(date=day, equity=round(equity, 2), lessons=lessons, vs_random_avg_r=None, **s)
