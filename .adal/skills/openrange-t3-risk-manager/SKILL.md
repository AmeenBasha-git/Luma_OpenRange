---
name: openrange-t3-risk-manager
description: Size each trade at a fixed % risk; enforce daily loss, position, sector and leverage limits.
---

# T3 Risk manager (Trader Agent, OpenRange)

Size each trade at a fixed % risk; enforce daily loss, position, sector and leverage limits.

- **Code:** `openrange.agents.trader.t3_risk` (function `run`)
- **Input:** Signal, account book
- **Output:** RiskDecision (Pydantic schema in `openrange/core/schemas.py`)
- **LLM:** Pure code. Never uses the LLM.

## How to use
Call `openrange.agents.trader.t3_risk.run(...)` with the inputs above. Every input and output is a Pydantic model, so results
can be passed straight to the next module. See `README.md` for the full daily flow.
