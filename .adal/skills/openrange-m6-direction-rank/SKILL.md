---
name: openrange-m6-direction-rank
description: Pick LONG/SHORT from the opening candle, rank by RVOL, keep the top 20 with a reason.
---

# M6 Direction & Rank (Analyst Agent, OpenRange)

Pick LONG/SHORT from the opening candle, rank by RVOL, keep the top 20 with a reason.

- **Code:** `openrange.agents.analyst.m6_rank` (function `run`)
- **Input:** InPlay, scores from M1-M4
- **Output:** Watchlist (Pydantic schema in `openrange/core/schemas.py`)
- **LLM:** Uses the LLM only to explain or score text; numbers come from code.

## How to use
Call `openrange.agents.analyst.m6_rank.run(...)` with the inputs above. Every input and output is a Pydantic model, so results
can be passed straight to the next module. See `README.md` for the full daily flow.
