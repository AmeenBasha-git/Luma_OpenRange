"""M2 Macro (daily, pre-market). Sets the long-term market bias.

Each area gets a score from -1 (bad for stocks) to +1 (good). The weighted average is the macro score.
Code does the scoring. The LLM only writes the plain-English narrative.
"""

from __future__ import annotations

from datetime import datetime

from openrange.core.llm import LLMClient, LLMError
from openrange.core.schemas import MacroNarrative, MacroSnapshot
from openrange.data.hub import DataHub
from openrange.data.macro import MacroReading

WEIGHTS = {"rates": 0.20, "yields": 0.15, "dollar": 0.10, "jobs": 0.10,
           "inflation": 0.15, "growth": 0.15, "fear": 0.15}
BIAS_THRESHOLD = 0.2


def _change(r: MacroReading) -> float:
    return r.value - r.value_1m_ago


def score_areas(m: dict[str, MacroReading]) -> dict[str, float]:
    """One score per area. Rising rates, yields, dollar, unemployment, inflation or fear = negative."""
    def falling_is_good(r: MacroReading, step: float) -> float:
        return max(-1.0, min(1.0, -_change(r) / step))

    def clamp(x: float) -> float:
        return max(-1.0, min(1.0, x))

    curve_penalty = 0.5 if m["y10"].value < m["y2"].value else 0.0     # inverted curve = recession warning

    vix = m["vix"].value
    if vix > 25:
        fear = -1.0
    elif vix < 15:
        fear = 1.0
    else:
        fear = 0.5 * falling_is_good(m["hy_spread"], 0.5)                # in between: credit spreads decide

    return {
        "rates": falling_is_good(m["fed_funds"], 0.25),
        "yields": clamp(falling_is_good(m["y10"], 0.25) - curve_penalty),
        "dollar": falling_is_good(m["dxy"], 2.0),
        "jobs": falling_is_good(m["unemployment"], 0.2),
        "inflation": falling_is_good(m["cpi_yoy"], 0.2),
        "growth": clamp((m["pmi"].value - 50) / 3),
        "fear": fear,
    }


def sector_tilt(m: dict[str, MacroReading]) -> dict[str, str]:
    tilt = {"tech": "0", "banks": "0", "energy": "0", "consumer": "0"}
    if _change(m["y10"]) > 0.1:
        tilt["tech"], tilt["banks"] = "-", "+"
    elif _change(m["y10"]) < -0.1:
        tilt["tech"] = "+"
    if _change(m["dxy"]) < -1:
        tilt["tech"] = "+"
    if _change(m["oil"]) > 3:
        tilt["energy"] = "+"
    return tilt


def run(data: DataHub, llm: LLMClient, as_of: datetime) -> MacroSnapshot:
    readings = data.macro.readings(as_of)
    areas = score_areas(readings)
    score = round(sum(WEIGHTS[a] * areas[a] for a in WEIGHTS), 3)
    score = max(-1.0, min(1.0, score))
    bias = "RISK_ON" if score > BIAS_THRESHOLD else "RISK_OFF" if score < -BIAS_THRESHOLD else "NEUTRAL"

    strongest = sorted(areas.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
    drivers = [f"{name} {'supports' if value > 0 else 'hurts'} stocks ({value:+.2f})" for name, value in strongest]
    events = data.calendar.economic_events(as_of.date(), as_of)

    narrative = "; ".join(drivers)                                  # code fallback
    try:
        prompt = (f"Write 2 sentences on the US stock market outlook. Macro score {score:+.2f} ({bias}). "
                  f"Drivers: {drivers}. Events today: {events or 'none'}. Do not invent numbers.")
        narrative = llm.generate(prompt, MacroNarrative, tier="smart").narrative
    except LLMError:
        pass

    return MacroSnapshot(as_of=as_of, bias=bias, score=score, drivers=drivers,
                         sector_tilt=sector_tilt(readings),
                         event_risk_today=", ".join(events) or None, narrative=narrative)
