"""T2 Rule gate. A signal passes only if ALL rules hold (rulebook 5A, no points system):

  1. in_play         RVOL >= min_rvol
  2. candle_matches  GREEN candle -> LONG only, RED candle -> SHORT only, DOJI -> never
  3. trend_matches   LONG only above the daily 200 EMA, SHORT only below it
  4. valid_stop      stop is on the losing side of the entry
"""

from __future__ import annotations

from openrange.core.schemas import GateDecision, Pick, Signal


def check(signal: Signal, pick: Pick, min_rvol: float) -> GateDecision:
    is_long = signal.side == "LONG"
    rules = {
        "in_play": pick.rvol >= min_rvol,
        "candle_matches": pick.or_candle == ("GREEN" if is_long else "RED"),
        "trend_matches": pick.above_ema200 == is_long,
        "valid_stop": signal.stop_price < signal.entry_price if is_long else signal.stop_price > signal.entry_price,
    }
    failed = [name for name, ok in rules.items() if not ok]
    return GateDecision(signal=signal, passed=not failed, failed_rules=failed)


def run(signals: list[Signal], picks: list[Pick], min_rvol: float) -> list[GateDecision]:
    by_ticker = {p.ticker: p for p in picks}
    return [check(s, by_ticker[s.ticker], min_rvol) for s in signals]
