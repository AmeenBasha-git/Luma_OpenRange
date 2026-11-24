---
name: openrange-t6-journal-lessons
description: Daily stats (win rate, R, expectancy) and regime-tagged lessons for the Analyst.
---

# T6 Journal & Lessons (Trader Agent, OpenRange)

Daily stats (win rate, R, expectancy) and regime-tagged lessons for the Analyst.

- **Code:** `openrange.agents.trader.t6_journal` (function `run`)
- **Input:** trades, equity, regime
- **Output:** DailyReport (Pydantic schema in `openrange/core/schemas.py`)
- **LLM:** Uses the LLM only to explain or score text; numbers come from code.

## How to use
Call `openrange.agents.trader.t6_journal.run(...)` with the inputs above. Every input and output is a Pydantic model, so results
can be passed straight to the next module. See `README.md` for the full daily flow.
