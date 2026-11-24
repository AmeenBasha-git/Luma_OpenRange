---
name: openrange-m2-macro
description: Score rates, yields, dollar, jobs, inflation, growth and fear into a RISK_ON/RISK_OFF bias.
---

# M2 Macro (Analyst Agent, OpenRange)

Score rates, yields, dollar, jobs, inflation, growth and fear into a RISK_ON/RISK_OFF bias.

- **Code:** `openrange.agents.analyst.m2_macro` (function `run`)
- **Input:** macro readings, economic calendar
- **Output:** MacroSnapshot (Pydantic schema in `openrange/core/schemas.py`)
- **LLM:** Uses the LLM only to explain or score text; numbers come from code.

## How to use
Call `openrange.agents.analyst.m2_macro.run(...)` with the inputs above. Every input and output is a Pydantic model, so results
can be passed straight to the next module. See `README.md` for the full daily flow.
