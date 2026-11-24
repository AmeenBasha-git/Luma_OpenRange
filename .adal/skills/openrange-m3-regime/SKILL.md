---
name: openrange-m3-regime
description: Label the market BULL/BEAR/SIDEWAYS/HIGH_VOL from SPY; sets position size.
---

# M3 Regime (Analyst Agent, OpenRange)

Label the market BULL/BEAR/SIDEWAYS/HIGH_VOL from SPY; sets position size.

- **Code:** `openrange.agents.analyst.m3_regime` (function `run`)
- **Input:** SPY daily bars, universe
- **Output:** RegimeState (Pydantic schema in `openrange/core/schemas.py`)
- **LLM:** Uses the LLM only to explain or score text; numbers come from code.

## How to use
Call `openrange.agents.analyst.m3_regime.run(...)` with the inputs above. Every input and output is a Pydantic model, so results
can be passed straight to the next module. See `README.md` for the full daily flow.
