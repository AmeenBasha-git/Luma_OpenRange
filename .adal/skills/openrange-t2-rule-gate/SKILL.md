---
name: openrange-t2-rule-gate
description: Pass a signal only if in play, candle direction matches, and the 200 EMA side matches.
---

# T2 Rule gate (Trader Agent, OpenRange)

Pass a signal only if in play, candle direction matches, and the 200 EMA side matches.

- **Code:** `openrange.agents.trader.t2_gate` (function `run`)
- **Input:** Signal, Pick
- **Output:** GateDecision (Pydantic schema in `openrange/core/schemas.py`)
- **LLM:** Pure code. Never uses the LLM.

## How to use
Call `openrange.agents.trader.t2_gate.run(...)` with the inputs above. Every input and output is a Pydantic model, so results
can be passed straight to the next module. See `README.md` for the full daily flow.
