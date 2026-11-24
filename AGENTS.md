# OpenRange: context for agent harnesses (AdaL loads this every turn)

OpenRange is a two-agent paper-trading system for US stocks.
- Analyst Agent (`openrange/agents/analyst/`) decides WHAT to trade.
- Trader Agent (`openrange/agents/trader/`) decides WHEN and HOW.
- They talk only through the message bus (`openrange/platform/bus.py`; BAND room when enabled).

Hard rules:
1. The LLM never places orders. Trader modules T1-T5 are pure code.
2. Risk limits in `config/settings.yaml` are never changed by an agent.
3. Answer with the JSON requested, no extra text. Never invent numbers.

Skills for every module: `.adal/skills/openrange-*/SKILL.md`. Data schemas: `openrange/core/schemas.py`.
