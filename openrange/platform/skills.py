"""Every OpenRange module packaged as a reusable skill.

    python -m openrange.platform.skills

writes one skill folder per module, in two places:
    .adal/skills/<skill>/SKILL.md          AdaL loads these on demand (project skills)
    skills/<skill>/SKILL.md + skill.json   the package we publish to the Finch skill market

A SKILL.md has YAML front matter (name, description) and plain instructions.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from openrange.core.config import PROJECT_ROOT


@dataclass(frozen=True)
class Skill:
    agent: str
    id: str
    name: str
    module: str
    uses_llm: bool
    description: str
    inputs: str
    outputs: str

    @property
    def slug(self) -> str:
        return f"openrange-{self.id.lower()}-{self.name.lower().replace(' & ', '-').replace(' ', '-')}"


SKILLS = [
    Skill("analyst", "M1", "Fundamental screen", "openrange.agents.analyst.m1_fundamental", False,
          "Keep liquid quality stocks: price, volume and ATR filters plus Piotroski F-score >= 6.",
          "universe, financials", "FundamentalScore per stock"),
    Skill("analyst", "M2", "Macro", "openrange.agents.analyst.m2_macro", True,
          "Score rates, yields, dollar, jobs, inflation, growth and fear into a RISK_ON/RISK_OFF bias.",
          "macro readings, economic calendar", "MacroSnapshot"),
    Skill("analyst", "M3", "Regime", "openrange.agents.analyst.m3_regime", True,
          "Label the market BULL/BEAR/SIDEWAYS/HIGH_VOL from SPY; sets position size.",
          "SPY daily bars, universe", "RegimeState"),
    Skill("analyst", "M4", "Sentiment", "openrange.agents.analyst.m4_sentiment", True,
          "Score news, Reddit and StockTwits sentiment 0-10 with a hype warning.",
          "headlines, social stats", "SentimentScore per stock"),
    Skill("analyst", "M5", "Stocks in Play", "openrange.agents.analyst.m5_in_play", False,
          "Find stocks whose first 5-minute candle volume is at least 1x its 14-day average (RVOL).",
          "5-minute bars, opening volume history", "InPlay per stock"),
    Skill("analyst", "M6", "Direction & Rank", "openrange.agents.analyst.m6_rank", True,
          "Pick LONG/SHORT from the opening candle, rank by RVOL, keep the top 20 with a reason.",
          "InPlay, scores from M1-M4", "Watchlist"),
    Skill("trader", "T1", "ORB signal", "openrange.agents.trader.t1_signals", False,
          "Opening Range Breakout: stop entry at the 5-minute range high/low, stop = 10% of daily ATR.",
          "Watchlist picks", "Signal per pick"),
    Skill("trader", "T2", "Rule gate", "openrange.agents.trader.t2_gate", False,
          "Pass a signal only if in play, candle direction matches, and the 200 EMA side matches.",
          "Signal, Pick", "GateDecision"),
    Skill("trader", "T3", "Risk manager", "openrange.agents.trader.t3_risk", False,
          "Size each trade at a fixed % risk; enforce daily loss, position, sector and leverage limits.",
          "Signal, account book", "RiskDecision"),
    Skill("trader", "T4", "Execution", "openrange.agents.trader.t4_broker", False,
          "Place stop-entry orders with protective stops in the simulator or Alpaca paper account.",
          "OrderIntent, bars", "Fill"),
    Skill("trader", "T5", "Monitor", "openrange.agents.trader.t5_monitor", False,
          "Turn closed positions into trades and close everything at 15:55.",
          "positions, fills", "Trade"),
    Skill("trader", "T6", "Journal & Lessons", "openrange.agents.trader.t6_journal", True,
          "Daily stats (win rate, R, expectancy) and regime-tagged lessons for the Analyst.",
          "trades, equity, regime", "DailyReport"),
]


def skill_markdown(s: Skill) -> str:
    llm_note = ("Uses the LLM only to explain or score text; numbers come from code."
                if s.uses_llm else "Pure code. Never uses the LLM.")
    return f"""---
name: {s.slug}
description: {s.description}
---

# {s.id} {s.name} ({s.agent.title()} Agent, OpenRange)

{s.description}

- **Code:** `{s.module}` (function `run`)
- **Input:** {s.inputs}
- **Output:** {s.outputs} (Pydantic schema in `openrange/core/schemas.py`)
- **LLM:** {llm_note}

## How to use
Call `{s.module}.run(...)` with the inputs above. Every input and output is a Pydantic model, so results
can be passed straight to the next module. See `README.md` for the full daily flow.
"""


def export() -> list[str]:
    written = []
    for s in SKILLS:
        text = skill_markdown(s)
        for folder in (PROJECT_ROOT / ".adal" / "skills" / s.slug, PROJECT_ROOT / "skills" / s.slug):
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "SKILL.md").write_text(text, encoding="utf-8")
            written.append(str(folder / "SKILL.md"))
        manifest = {**asdict(s), "slug": s.slug, "project": "OpenRange", "version": "0.1.0", "license": "MIT"}
        (PROJECT_ROOT / "skills" / s.slug / "skill.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return written


if __name__ == "__main__":
    files = export()
    print(f"Wrote {len(files)} SKILL.md files (.adal/skills for AdaL, skills/ for Finch)")
