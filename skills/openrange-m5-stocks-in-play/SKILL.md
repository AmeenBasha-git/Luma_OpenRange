---
name: openrange-m5-stocks-in-play
description: Find stocks whose first 5-minute candle volume is at least 1x its 14-day average (RVOL).
---

# M5 Stocks in Play (Analyst Agent, OpenRange)

Find stocks whose first 5-minute candle volume is at least 1x its 14-day average (RVOL).

- **Code:** `openrange.agents.analyst.m5_in_play` (function `run`)
- **Input:** 5-minute bars, opening volume history
- **Output:** InPlay per stock (Pydantic schema in `openrange/core/schemas.py`)
- **LLM:** Pure code. Never uses the LLM.

## How to use
Call `openrange.agents.analyst.m5_in_play.run(...)` with the inputs above. Every input and output is a Pydantic model, so results
can be passed straight to the next module. See `README.md` for the full daily flow.
