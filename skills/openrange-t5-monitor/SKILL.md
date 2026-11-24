---
name: openrange-t5-monitor
description: Turn closed positions into trades and close everything at 15:55.
---

# T5 Monitor (Trader Agent, OpenRange)

Turn closed positions into trades and close everything at 15:55.

- **Code:** `openrange.agents.trader.t5_monitor` (function `run`)
- **Input:** positions, fills
- **Output:** Trade (Pydantic schema in `openrange/core/schemas.py`)
- **LLM:** Pure code. Never uses the LLM.

## How to use
Call `openrange.agents.trader.t5_monitor.run(...)` with the inputs above. Every input and output is a Pydantic model, so results
can be passed straight to the next module. See `README.md` for the full daily flow.
