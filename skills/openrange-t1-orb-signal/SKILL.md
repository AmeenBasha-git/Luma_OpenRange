---
name: openrange-t1-orb-signal
description: Opening Range Breakout: stop entry at the 5-minute range high/low, stop = 10% of daily ATR.
---

# T1 ORB signal (Trader Agent, OpenRange)

Opening Range Breakout: stop entry at the 5-minute range high/low, stop = 10% of daily ATR.

- **Code:** `openrange.agents.trader.t1_signals` (function `run`)
- **Input:** Watchlist picks
- **Output:** Signal per pick (Pydantic schema in `openrange/core/schemas.py`)
- **LLM:** Pure code. Never uses the LLM.

## How to use
Call `openrange.agents.trader.t1_signals.run(...)` with the inputs above. Every input and output is a Pydantic model, so results
can be passed straight to the next module. See `README.md` for the full daily flow.
