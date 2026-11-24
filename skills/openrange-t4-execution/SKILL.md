---
name: openrange-t4-execution
description: Place stop-entry orders with protective stops in the simulator or Alpaca paper account.
---

# T4 Execution (Trader Agent, OpenRange)

Place stop-entry orders with protective stops in the simulator or Alpaca paper account.

- **Code:** `openrange.agents.trader.t4_broker` (function `run`)
- **Input:** OrderIntent, bars
- **Output:** Fill (Pydantic schema in `openrange/core/schemas.py`)
- **LLM:** Pure code. Never uses the LLM.

## How to use
Call `openrange.agents.trader.t4_broker.run(...)` with the inputs above. Every input and output is a Pydantic model, so results
can be passed straight to the next module. See `README.md` for the full daily flow.
