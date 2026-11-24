---
name: openrange-m1-fundamental-screen
description: Keep liquid quality stocks: price, volume and ATR filters plus Piotroski F-score >= 6.
---

# M1 Fundamental screen (Analyst Agent, OpenRange)

Keep liquid quality stocks: price, volume and ATR filters plus Piotroski F-score >= 6.

- **Code:** `openrange.agents.analyst.m1_fundamental` (function `run`)
- **Input:** universe, financials
- **Output:** FundamentalScore per stock (Pydantic schema in `openrange/core/schemas.py`)
- **LLM:** Pure code. Never uses the LLM.

## How to use
Call `openrange.agents.analyst.m1_fundamental.run(...)` with the inputs above. Every input and output is a Pydantic model, so results
can be passed straight to the next module. See `README.md` for the full daily flow.
