# OpenRange

Two AI agents paper-trade US stocks.
**Analyst Agent** decides *what* to trade. **Trader Agent** decides *when and how*.
The LLM explains; code executes. The LLM never places an order.

Full design: [`PROJECT_SPEC.md`](PROJECT_SPEC.md) · Requirements: [`docs/PRD.md`](docs/PRD.md)

---

## 1. Setup (once)

```bash
python -m venv .venv --system-site-packages
.venv\Scripts\activate            # Windows   (Mac/Linux: source .venv/bin/activate)
pip install -e ".[dashboard,dev]"
copy .env.example .env            # then fill in keys (not needed for fake mode)
```

## 2. Run it

| What | Command |
|---|---|
| One fake trading day (08:00 → 16:15) | `python scripts/run_fake_day.py` |
| A different day | `python scripts/run_fake_day.py 2026-11-18` |
| Download real prices (Yahoo, ~3 min) | `python -m openrange.data.yahoo download` |
| Backtest on fake prices | `python -m openrange.backtest.runner --start 2026-09-01 --days 20` |
| Backtest on real prices | `python -m openrange.backtest.runner --start 2026-09-21 --days 60 --data yahoo` |
| Same rules on random stocks (baseline) | add `--selection random` |
| Trade statistics of the last backtest | `python -m openrange.backtest.report` |
| Dashboard | `python -m streamlit run dashboard/app.py` → open http://localhost:8501 |
| Tests | `pytest` |
| Lint | `ruff check .` |
| Live scheduler (real clock) | `python -m openrange.orchestrator.scheduler` |
| Live scheduler, one agent per process | `python -m openrange.orchestrator.scheduler --role analyst` (or `trader`) |
| Export skills (AdaL + Finch) | `python -m openrange.platform.skills` |
| Search the Finch skill market | `python -m openrange.platform.finch trading` |
| Deploy both agents to Agent37 | `python -m openrange.platform.agent37 deploy` |

## 3. How the code is laid out

Folders follow the architecture diagram. One file = one module.

```
config/
  settings.yaml        every number: risk, strategy, costs, LLM, paths
  market_us.yaml       session times, schedule, universe, macro series
openrange/
  core/                shared building blocks
    schemas.py         ALL data passed between modules (read this first)
    config.py          loads the YAML + .env
    db.py              SQLite: one table per record type
    clock.py           LiveClock / ReplayClock
    llm.py             one LLM client: FakeLLM / Gemini / Claude
    indicators.py      EMA, ATR, volatility, candle colour
    log.py             logging
  data/                data adapters (every call takes as_of: no look-ahead)
    prices.py  fundamentals.py  macro.py  news.py  social.py  calendar.py
    synthetic.py       fake market data for fake mode and tests
    hub.py             DataHub: all adapters in one object
  agents/
    analyst/           Agent 1: WHAT to trade
      agent.py         run_weekly / run_premarket / run_open
      m1_fundamental.py  m2_macro.py  m3_regime.py  m4_sentiment.py  m5_in_play.py  m6_rank.py
    trader/            Agent 2: WHEN and HOW
      agent.py         on_open / on_tick / on_close / review
      t1_signals.py  t2_gate.py  t3_risk.py  t4_broker.py  t5_monitor.py  t6_journal.py
  platform/            sponsor tools (each one falls back to local when keys are missing)
    bus.py             BAND: agent-to-agent messages (LocalBus fallback)
    lyzr.py            Lyzr: Analyst LLM calls with guardrails + audit log
    adal.py            AdaL: harness for the Trader's daily review
    skills.py          12 modules as skills (.adal/skills for AdaL, skills/ for Finch)
    finch.py           Finch skill-market search
    agent37.py         Agent37: one cloud sandbox per agent
  orchestrator/
    wiring.py          builds the system from settings
    jobs.py            the day's jobs + run_day (replay)
    scheduler.py       real-time schedule (APScheduler), --role analyst|trader|both
  backtest/runner.py   many days through the same agents
agents_harness/        AdaL personality per agent (SYSTEM.md)
skills/                Finch skill packages      .adal/skills/  AdaL skills      AGENTS.md  harness context
Dockerfile             image for Agent37 sandboxes
dashboard/app.py       Streamlit: Analyst | Trader | P&L | Stats
scripts/run_fake_day.py
tests/                 one test file per concern
```

## 4. One trading day

| Time (ET) | Who | What |
|---|---|---|
| Sun 18:00 | Analyst M1 | Fundamental screen (liquidity + Piotroski ≥ 6) |
| 08:00 | Analyst M2–M4 | Macro bias, market regime, sentiment on candidates |
| 09:35 | Analyst M5–M6 | Stocks in play (RVOL ≥ 1) → top 20 LONG/SHORT → **watchlist on the bus** |
| 09:35 | Trader T1–T4 | ORB signals → rule gate → risk sizing → stop orders |
| 09:40–15:50 | Trader T4–T5 | Every 5 min: fills, stops, daily-loss check |
| 15:55 | Trader T5 | Close everything |
| 16:15 | Trader T6 | Stats + lessons → **lessons on the bus** → Analyst reads them next morning |

## 5. Safety rules (enforced by tests)

1. Exactly two agents; they only talk through the bus (`platform/bus.py`).
2. Trader modules T1–T5 never import the LLM (`tests/test_no_llm_in_order_path.py`).
3. Risk limits are code and can't be overridden (`tests/test_risk_limits.py`).
4. No adapter returns data after `as_of` (`tests/test_asof_guard.py`).
5. If the LLM fails, every module falls back to its code result and trading continues.

## 6. Status

| Phase | What | Status |
|---|---|---|
| 0 | Full skeleton on fake data, tests, dashboard | ✅ done |
| 1 | Real price data (Yahoo) + real ORB backtest + random baseline | ✅ done |
| 2 | Real Analyst data: FRED macro, HMM regime, news/Reddit sentiment, Gemini | |
| 3 | Backtest on history, picks vs random, SPY comparison | |
| 4 | Sponsor tools: BAND, Lyzr, AdaL, Finch, Agent37 | ✅ code done, tested with mocks; needs your accounts → [`docs/SPONSOR_SETUP.md`](docs/SPONSOR_SETUP.md) |
| 5 | Alpaca paper trading + demo | |

**Data note:** `data: fake` = random prices (shows the plumbing works). `data: yahoo` = real prices for ~147 stocks;
Yahoo keeps only ~60 days of 5-minute bars, and re-running the download adds new days to the saved history.
In Phase 1 only prices are real, so the Piotroski and sentiment filters are switched off in real-data backtests.

*Simulation only. Not financial advice.*
