---
name: openrange-m4-sentiment
description: Score news, Reddit and StockTwits sentiment 0-10 with a hype warning.
---

# M4 Sentiment (Analyst Agent, OpenRange)

Score news, Reddit and StockTwits sentiment 0-10 with a hype warning.

- **Code:** `openrange.agents.analyst.m4_sentiment` (function `run`)
- **Input:** headlines, social stats
- **Output:** SentimentScore per stock (Pydantic schema in `openrange/core/schemas.py`)
- **LLM:** Uses the LLM only to explain or score text; numbers come from code.

## How to use
Call `openrange.agents.analyst.m4_sentiment.run(...)` with the inputs above. Every input and output is a Pydantic model, so results
can be passed straight to the next module. See `README.md` for the full daily flow.
