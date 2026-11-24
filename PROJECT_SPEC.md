# Fintech Multi-Agent Trading System — Project Spec & Discussion Log

> **Purpose of this file:** Complete record of everything decided so far, so the discussion can
> be resumed in a new Claude Code session. Say: *"Read PROJECT_SPEC.md and continue."*
>
> **Last updated:** 2026-11-23
> **Status:** Project definition phase (architecture NOT designed yet — finalize open questions first)

---

## 0. Hackathon Problem Statement

> **"Analyst Agent gathers market data; Trader Agent executes simulated trades from those insights."**

**Hackathon constraint:** Only **two agents** allowed.
**Our approach:** 2 agents, each with many internal **modules** (skills/tools). This keeps the
intelligence of a 12+ agent design while satisfying the 2-agent rule.

- **Agent 1 = Analyst Agent** → decides **WHAT** to trade and **WHICH DIRECTION**
- **Agent 2 = Trading Agent** → decides **WHEN** and **HOW** to trade, and manages the trade

> ⚠️ **Action item:** Ask organizers: *"For the Finance track, is a simulated (paper) trading
> system on US equities acceptable?"* and confirm that internal modules don't count as extra agents.

---

## 1. Basic Concepts (learning notes)

- **Agent** = LLM (Claude) + a **role** + **tools** (Python functions it can call) + a **loop**
  (think → use tool → observe → repeat).
- **Multi-agent** = several agents with one job each, passing **structured data (JSON)** to each other.
- **Module** = one specific job inside an agent (e.g., "Macro Analysis" inside the Analyst Agent).
- **Orchestrator** = controller deciding who runs next (plain Python or LangGraph).
- **Golden rule:** LLM *suggests and explains*; **deterministic code enforces** risk limits and
  places orders. The LLM never directly touches money.
- **Market regime** = the market's current "mood": Bull / Bear / Sideways / High-Volatility.
  Usually detected with a **Hidden Markov Model (HMM)** on returns + volatility.
- **HMM (explained 2026-11-23):** The market has a *hidden* state (Bull/Bear/Sideways/High-Vol) that we
  can't see directly. We only see *clues*: daily returns + volatility. The HMM learns (1) what each state's
  clues look like and (2) how likely the market is to switch states (states are "sticky"). Then it tells us
  the most likely current state + a confidence. Unsupervised: we give it the number of states, and we name them
  ourselves afterwards by looking at each state's avg return/volatility.
- **Expectancy** = `(Win% × AvgWin) − (Loss% × AvgLoss) − Costs`. Positive expectancy = edge.
  You can win <50% of trades and still profit if winners are bigger than losers (R:R ≥ 2).
- **Alpha** = return beyond what the market/benchmark gives. We prove it by comparing
  **our selected stocks vs. random stocks** using the same strategy.

---

## 2. Research Done

### 2.1 Reference open-source projects (GitHub)
| Project | What it is | What we take from it |
|---|---|---|
| **TauricResearch/TradingAgents** (Apache-2.0, LangGraph, paper arXiv 2412.20138) | Analysts (fundamental, sentiment, news, technical) → Bull/Bear researchers → Research Manager → Trader → 3 risk debaters → Portfolio Manager → Memory/Reflection. Supports Anthropic/OpenAI/Google/Ollama. Has `dataflows/vendors/` for yahoo, alpha_vantage, fred, reddit, stocktwits, sec_edgar, polymarket; `memory/reflection.py`; `backtest.py` | Framework inspiration, data-vendor layout, reflection/memory idea. **We do NOT copy it.** |
| **virattt/ai-hedge-fund** (~45k stars) | Valuation, sentiment, fundamentals, technicals, risk manager agents + backtester | Clean readable structure, backtester |
| **Open-Finance-Lab/AgenticTrading** | Research playground, FinAgent Orchestration Framework (NeurIPS 2025 workshop) | Orchestration ideas |
| **Quorai** (quorai.github.io) | Multi-agent LLM sandbox with daily SPY regime classifier that decides which analysts run | Regime-gated routing |
| **td-02/ai-native-hedge-fund** | Multi-agent pipeline with Regime + Benchmark-Relative Adjustment stage | Regime adjustment step |
| **Sakeeb91/market-regime-detection** (MIT) | HMM/GMM/change-point regime detection → strategy engine → backtester | Regime detector implementation reference |
| FinRobot, FinGPT, FinMem (AI4Finance etc.) | Finance agent platform / finance LLMs / memory-based trading agent | Ideas only (not verified in session) |

### 2.2 Key research papers
| Paper | Finding | How we use it |
|---|---|---|
| **Zarattini, Barbon & Aziz — "A Profitable Day Trading Strategy for the U.S. Equity Market"** (SSRN 4729284, 2024) | 5-min **ORB on "Stocks in Play" only**. Selection: opening-range relative volume ≥ 100% vs 14-day avg, take **top 20 by relative volume**. 2016–2023: ~1,600% net, Sharpe 2.81, 36% annual alpha. RVOL filter alone lifted returns 29% → 1,637%. QuantConnect replication: Sharpe ~2.4. | **Core of our stock selection + ORB execution.** Lesson: the **selection creates the alpha**, ORB just executes. |
| ORB replication on **index futures** (MQL5 blog) | Gross reproduced, **net zero after costs** | Always model costs; ORB on random/index instruments has no edge |
| Zarattini & Aziz — "Can Day Trading Really Be Profitable?" (SSRN 4416622, 2023) | Earlier ORB work | Background |
| **Anić, Barbon, Seiz & Zarattini** (arXiv 2510.26228) | LLM scores news for momentum stocks → improves selection & weighting; beats plain momentum out-of-sample | Basis of our **Sentiment module** |
| AI attractiveness scores (arXiv 2601.11958) | AI is best at picking **top performers** (top-20 long: FF5+Mom alpha 18.4 bp/day) | Use AI to **rank**, not to filter bad stocks |
| Automate Strategy Finding with LLM (arXiv 2409.06289) | Group factors into momentum / fundamental / liquidity, weight by market condition | **Regime-dependent weighting** in final score |
| NYU Shanghai thesis (2026) | Text-based and numeric rankings barely overlap → combine both | Final score combines news/social + numbers |
| MarketSenseAI (arXiv 2401.03737) | GPT-4 stock selection framework | Background |
| Market Regime Council (arXiv 2605.24490, NeurIPS 2026 poster) | Regime-dependent agent/credit weighting | Idea: weight modules by regime (scorecards) |
| Miyazaki et al. (arXiv 2602.23330) | Fine-grained task decomposition beats vague instructions | Write **specific, granular prompts** per module |
| Agent4Crypto (arXiv 2611.12269) | Market-feedback (RL) reweighting of agents | Idea for learning loop |
| Jia et al. (arXiv 2611.11657) | LLM analysts + rule-based execution | Validates: **LLM analyzes, code executes** |
| Classic finance (not searched, from knowledge) | Momentum (Jegadeesh & Titman), quality/profitability factors, **Piotroski F-score**, post-earnings-announcement drift (PEAD) | Fundamental screen + earnings surprise |

### 2.3 Tooling findings
- **Alpaca paper trading:** free, ~$100K simulated funds, real market data, no card, Python SDK
  `alpaca-py`, MCP server available. Paper fills don't model slippage/liquidity perfectly.
- Alpaca ran an "AI Trading Agents Hackathon" (Aug–Sep 2026) — this stack is well-trodden.

### 2.4 ORB "bad day" filter study on the S&P 500 (2026-11-23)
Full details and code: `research/orb_failure_days/` (README.md, scripts, results CSVs).
- **Test:** SPY **60-min ORB** (stop = other side of range, exit at close, $0.02/side cost), last 2 years
  (2024-11-21 → 2026-11-20, 487 trades), split into Y1/Y2, plus the year before (Dec 2023–Nov 2024) as out-of-sample.
  Data: Yahoo hourly SPY; checked against 5-min bars over 60 days (exact match on all 60 days).
- **Baseline:** about zero edge (avg **−0.00R**, win 48%, PF 1.00). Matches the research: ORB on an index has no edge by itself.
- **VIX level and big gaps are NOT reliable avoid-filters:** VIX ≥ 26 days averaged +0.24R; |gap| ≥ 100 SPX pts
  (15 days) averaged +0.18R, but signs flip year to year and samples are tiny. No bucket was statistically significant.
- **Only consistent warning:** **VIX rose > 10% the previous day** → stop-outs higher in all 3 years
  (42/30/44% vs 28/23/33%), avg −0.17R vs +0.03R (p = 0.08, suggestive, not proven).
- **Failures happen mostly on QUIET days:** the worst losses (both sides of the range broken) had low VIX (13–17),
  small gaps, and a narrow opening range. Narrow range (< 0.28× ATR) = more stop-outs in all 3 years, but the same avg R.
- **Not yet tested:** 5/15/30-min ORB over 2 years needs 1-min data (Yahoo gives only 60 days). Free fix: Alpaca keys.

---

## 3. Decisions Made (history)

1. Started with a 12+ agent idea: Regime, Pattern, Macro, Risk Manager, Bull vs Bear debate,
   Manager, Execution, Lesson (+ suggested Sentiment, Portfolio, Monitor, Scorecard, Explainer, etc.).
2. Review of that list: Regime = best idea; Pattern must be **code-detected** (LLMs hallucinate
   patterns); Risk & Execution must be **deterministic code**; Lessons must be **regime-tagged**.
3. **Hackathon allows only 2 agents** → compressed everything into **Analyst Agent + Trading Agent**
   with modules.
4. **Bull vs Bear debate: REMOVED.**
5. **Fundamental analysis moved to the TOP** of the Analyst Agent (select proper stocks first,
   then check macro/regime/sentiment on them).
6. Stock selection is research-based: **funnel** (Fundamental → … → Stocks in Play → Rank).
7. **Macro module expanded:** dollar, US interest rates/Fed, yields & curve, unemployment,
   inflation, growth, VIX/credit/oil, economic calendar → **long-term direction**.
8. **Sentiment expanded:** News + **Reddit** + StockTwits (X/Twitter skipped — expensive API).
9. **Market: US stocks** (hackathon doesn't restrict). Code designed **market-agnostic via config**
   so India (NSE) can be added later as a bonus story.
10. **200 EMA (daily)** = long-term direction filter in the Trading Agent.
11. Strategies: **ORB** + EMA pullback + VWAP + previous-day high/low + mean reversion,
    **chosen by regime**, gated by a **confluence score ≥ 7/10**.
    → **SUPERSEDED 2026-11-23 by backtest (Section 5A):** only **ORB on Stocks in Play + 200 EMA filter** passed.
    EMA/VWAP pullback and VWAP mean reversion lost money and were dropped. PDH/PDL break is on a watch list (too few trades).

---

## 4. AGENT 1 — ANALYST AGENT (WHAT + WHICH DIRECTION)

**Runs:** weekly (fundamentals) · pre-market (macro, regime, sentiment) · ~5 min after open (final picks)

**Funnel:**
```
~500 stocks → [1 FUNDAMENTAL] → ~100 → [2 MACRO] + [3 REGIME] → [4 SENTIMENT] (~30–50)
            → [5 STOCKS IN PLAY] (at open) → [6 DIRECTION & RANK] → Top 10–20 with LONG/SHORT
```
**Two-pass timing:** Pre-market pass (modules 1–4) builds a candidate list of ~30–50.
Post-open pass (modules 5–6, after first 5 minutes) produces the final top list —
because relative volume needs the first 5 minutes of trading.

### Module 1 — 🏦 Fundamental Screen (weekly)
Goal: filter ~500 liquid US stocks to ~100 quality companies.

| Tool | Function |
|---|---|
| `get_universe()` | S&P 500 / Russell 1000; filters: price > $10, avg volume > 1M, sufficient ATR |
| `get_financials(ticker)` | Revenue, earnings, margins, debt, cash flow |
| `calc_piotroski_score(ticker)` | F-score 0–9; keep **≥ 6** |
| `get_valuation(ticker)` | P/E, P/S, PEG vs. sector |
| `get_earnings_calendar()` | Upcoming / recent earnings dates |
| `get_earnings_surprise(ticker)` | Beat/miss vs. estimates (post-earnings drift) |

**Output:** quality watchlist + fundamental score (0–1) per stock.

### Module 2 — 🌍 Macro Analysis (daily; sets LONG-TERM direction)
| Area | Indicators | Tool | Typical effect on stocks |
|---|---|---|---|
| 💵 Dollar | DXY trend (20/50-day) | `get_dxy()` | Strong $ 📉 (hurts multinationals/EM); weak $ 📈 |
| 🏦 Interest rates | Fed funds rate, last FOMC decision, next FOMC date | `get_fed_rate()`, `get_fomc_calendar()` | Hikes 📉, cuts 📈 |
| 📈 Bonds | 10Y & 2Y yields, **yield curve (10Y−2Y)** | `get_yields()` | Rising yields hurt tech/growth; inverted curve = recession warning |
| 👷 Jobs | Unemployment rate, Non-Farm Payrolls, weekly jobless claims | `get_labor_data()` | Rising unemployment 📉 (but can be 📈 if it means rate cuts — context matters) |
| 🔥 Inflation | CPI, Core CPI, PCE (actual vs. expected) | `get_inflation()` | Hot 📉 (more hikes), cooling 📈 |
| 🏭 Growth | ISM PMI (>50 = expansion), GDP | `get_growth_data()` | Growth 📈 |
| 😨 Fear/stress | VIX (>25 = fear), high-yield credit spreads, oil | `get_risk_gauges()` | Spikes = risk-off |
| 📅 Events | CPI / NFP / FOMC / earnings today | `get_economic_calendar()` | Event risk |

**Logic:**
- Score each area −1…+1 → weighted **macro score**.
- **Long-term direction = macro score + index 200 EMA.** Agree → strong direction; disagree → neutral, smaller size.
- **Sector tilt:** e.g., rising yields → avoid tech, favor banks; weak dollar → favor multinationals.
- **Event-day guard:** FOMC/CPI/NFP days → reduce size or wait until after release.
- **Point-in-time data:** use **ALFRED** (FRED vintages) in backtests to avoid look-ahead bias from revisions.

**Data:** FRED API (free key) for rates/yields/labor/inflation/PMI; yfinance for DXY, VIX, oil.

**Output example:**
```json
{"macro_bias":"RISK_ON","score":0.6,"horizon":"1-3 months",
 "drivers":["Fed cut 25bp","CPI cooling","DXY falling"],
 "sector_tilt":{"tech":"+","banks":"-","energy":"0"},
 "event_risk_today":"CPI 8:30 ET -> reduce size until after"}
```

### Module 3 — 🌦️ Regime Detection (daily)
| Tool | Function |
|---|---|
| `detect_regime(index="SPY")` | HMM (`hmmlearn`, 3–4 states) on returns + volatility → **Bull / Bear / Sideways / High-Vol** + confidence; LLM explains in plain English |
| `get_market_breadth()` | % of S&P stocks above 200 EMA (confirms regime) |
| `get_sector_strength()` | Leading/lagging sectors vs. index |

**Output:** regime label → **controls strategy selection and max position size** in Agent 2.

**PROPOSED (2026-11-23, user raised that regime changes during the day): TWO-LAYER REGIME**
- **Layer 1, Daily regime (Analyst Agent, pre-market):** HMM on daily SPY returns + volatility. Sets the
  background: direction bias + max size for the day. Changes rarely (weeks).
- **Layer 2, Intraday regime (Trading Agent, re-checked every 5 min on 5-min bars, SPY + each stock):**
  | Intraday state | Rule |
  |---|---|
  | TREND UP | ADX(14) > 25, price > VWAP, VWAP rising |
  | TREND DOWN | ADX(14) > 25, price < VWAP, VWAP falling |
  | CONSOLIDATION | ADX < 20, price keeps crossing VWAP, Bollinger width narrow / price inside a range |
  | CHOPPY / HIGH-VOL | 5-min ATR > 1.5x its normal, but ADX low (big moves, no direction) |
  - A state switch needs 2 bars in a row (10 min) to confirm → avoids flip-flopping.
  - Intraday state picks the strategy *right now*: trend → ORB/EMA pullback/VWAP continuation;
    consolidation → no trend entries, wait for range breakout (or mean reversion if allowed);
    choppy → no new trades.
  - Trend entries in the opposite direction to the daily regime are not allowed (daily layer = boss).
Caution: regime models overfit — validate out-of-sample (e.g., train 2020–2023, test 2024–2025).

### Module 4 — 📰 Sentiment Analysis (daily, on ~30–50 candidates)
| Tool | Source | Function |
|---|---|---|
| `get_news(ticker)` | News API / yfinance | Headlines → LLM sentiment score + catalyst |
| `get_reddit_mentions(ticker)` | r/wallstreetbets, r/stocks, r/investing | Mention count, **spike vs. 7-day avg**, LLM-scored tone |
| `get_stocktwits(ticker)` | StockTwits | Bullish/bearish tag ratio |
| `detect_hype(ticker)` | combined | Flags extreme euphoria (contrarian warning) |

**Score = News 60% + Reddit 25% + StockTwits 15%** (tunable). Filter bots/new accounts/duplicates.
**Rules:** mention spikes = "in play" signal; moderate positive = bullish; extreme euphoria = caution.
**Limits:** Reddit API free for non-commercial w/ OAuth, rate-limited (verify terms). Historical
Reddit data is hard to get → social sentiment is mostly **live / recent-history**; tell judges.

**Output example:**
```json
{"ticker":"NVDA","sentiment":0.55,"mention_spike":3.2,"hype_warning":false,
 "catalyst":"Earnings beat + raised guidance",
 "crowd_says":"Retail bullish on AI demand; some valuation worries"}
```

### Module 5 — 🔥 Stocks in Play (~5 min after open)
| Tool | Function |
|---|---|
| `get_premarket_gap(ticker)` | Gap % vs. previous close |
| `calc_relative_volume(ticker)` | First-5-min volume ÷ 14-day avg of the same window; keep **≥ 100%** |

Based on Zarattini et al. This is where most of the alpha comes from.

### Module 6 — 🧭 Direction & Rank (final)
| Tool | Function |
|---|---|
| `calc_final_score(ticker)` | Combines fundamental + macro + regime + sentiment + relative volume + 200 EMA side + momentum (weights depend on regime) |
| `assign_direction(ticker)` | LONG / SHORT / SKIP |
| `publish_watchlist()` | Sends **top 10–20** to Agent 2 |

### Agent 1 → Agent 2 handoff (JSON contract)
```json
{"date":"2026-11-24","regime":"BULL","macro_bias":"RISK_ON","event_risk":"none",
 "picks":[{"ticker":"NVDA","bias":"LONG","conviction":0.82,"rvol":3.1,
           "catalyst":"Earnings beat","reason":"..."}]}
```

---

## 5. AGENT 2 — TRADING AGENT (WHEN + HOW + MANAGE)

**Runs:** during market hours, loop every 1–5 minutes. Only trades Agent 1's picks, only in the given direction.

### Module 1 — 📈 Trend Filter
| Tool | Rule |
|---|---|
| `get_ema(ticker, 200, "1d")` | Price above daily 200 EMA → **longs only**; below → **shorts only** |
| `check_alignment(ticker)` | Analyst bias and 200 EMA must agree, else skip |

Note: 200 EMA is a slow **direction filter**, never an entry signal.

### Module 2 — 🎯 Strategy Engine (regime selects strategies)
> ⚠️ **The table below is the ORIGINAL idea. After the backtest, the live rules are in Section 5A.**
| Tool / Strategy | Regime | Entry rule |
|---|---|---|
| `orb_signal()` — **Opening Range Breakout** | Bull / Bear (High-Vol: wider range, smaller size) | Break of first 5- or 15-min high/low, in bias direction, with volume |
| `ema_pullback_signal()` — 9/21 EMA pullback | Bull / Bear | Pullback to 21 EMA and bounce |
| `vwap_signal()` — VWAP reclaim/rejection | All | Price crosses VWAP with volume |
| `pdh_pdl_break()` — previous-day high/low | Bull / Bear | Break of yesterday's key level |
| `mean_reversion_signal()` — RSI + Bollinger | **Sideways only** | Stretched price returns toward the mean |

Regime → strategy map: **Trending** → ORB, EMA pullback, VWAP, PDH/PDL · **Sideways** → VWAP mean
reversion, RSI+Bollinger · **High-Vol** → ORB wide range + half size, or no trading.

### Module 3 — ✅ Confluence Score (`score_setup(signal)`; trade only if ≥ 7/10)
| Check | Points |
|---|---|
| Matches Analyst bias | +3 |
| Correct side of 200 EMA | +2 |
| Strategy fits regime | +2 |
| Volume above average | +1 |
| Reward:Risk ≥ 2 | +1 |
| Sentiment/catalyst supports | +1 |

More trades come from **more stocks × more strategies**, NOT from lowering the threshold.

### Module 4 — 🛡️ Risk Manager (hard-coded; LLM cannot override)
| Tool | Rule |
|---|---|
| `calc_position_size()` | Risk 0.5–1% of account per trade, ATR-based stop |
| `regime_size_cap()` | High-Vol → half size; event day → half size |
| `check_daily_loss()` | Stop trading for the day at −2% |
| `check_exposure()` | Max 5 open positions, max 2 per sector |
| `set_stop_target()` | Stop-loss + take-profit (target ≥ 2R) |

### Module 5 — 💹 Execution (deterministic code, no LLM)
| Tool | Function |
|---|---|
| `place_order()` | **Alpaca paper trading** or our own simulated broker |
| `simulate_costs()` | Slippage + fees (keeps results honest) |
| `cancel_order()` / `close_position()` | Exit handling |

### Module 6 — 👁️ Monitor
| Tool | Function |
|---|---|
| `track_positions()` | Live P&L per position |
| `trail_stop()` | Move stop to breakeven at +1R, then trail |
| `regime_exit_check()` | Exit if regime/macro flips intraday |
| `eod_flatten()` | Close all intraday positions before market close |
| `push_to_dashboard()` | Stream everything to the dashboard |

### Module 7 — 📚 Journal & Lessons (post-market)
| Tool | Function |
|---|---|
| `log_trade()` | Entry, exit, reason, score, regime |
| `calc_expectancy()` | Win %, avg win/loss, **expectancy**, Sharpe, max drawdown |
| `write_lessons()` | LLM review → **regime-tagged** lessons fed back to Agent 1 |
| `compare_vs_random()` | Our picks vs. random stocks — **proof of alpha** |

---

## 5A. STRATEGY RULEBOOK (backtested 2026-11-23) — THIS IS WHAT AGENT 2 TRADES

### Strategy A (ADOPTED): ORB on Stocks in Play, Zarattini-style
| Item | Rule |
|---|---|
| Timeframe | **5-minute candles.** Opening range (OR) = **first 5-min candle, 9:30–9:35 ET** |
| Universe (pre-market) | Analyst candidates with price > $5, 14-day avg volume > 1M shares, 14-day daily ATR > $0.50 |
| Stocks in Play (9:35) | **RVOL** = volume of the 9:30–9:35 candle ÷ avg of that same candle over the last 14 days. Keep **RVOL ≥ 1.0**, take the **top 20 by RVOL** |
| Direction | First candle **green → LONG only**. **Red → SHORT only**. Doji → skip |
| Trend filter | LONG only if yesterday's close is **above the daily 200 EMA**; SHORT only if **below**. Otherwise skip |
| Entry | **Stop order** at OR high (long) / OR low (short). Starts at 9:35 and stays active all day (as tested) |
| Stop-loss | **10% of the 14-day daily ATR** from the entry price (e.g. ATR $4 → stop $0.40 away) |
| Take-profit | **None. Exit at the close (15:55 ET).** Fixed 2R/3R targets and moving the stop to breakeven tested worse |
| Max trades | 1 per stock per day |
| Costs modeled | $0.0035/share commission + $0.01/share slippage, each side |
| Expected profile | **Low win rate (~17–40%) but big winners.** Many small −1R losses, a few +3R…+10R days |

### Backtest results (R = 1 unit of risk; net of costs)
| Test | Trades | Win % | Avg R/trade | Profit factor | t-stat | Notes |
|---|---|---|---|---|---|---|
| **2-yr hourly, 60-min ORB, in play + 200 EMA, stop 25% ATR, EOD** (Jan 2024–Nov 2026) | 650 | 40% | **+0.13** | 1.24 | 2.0 | Y1 +0.21, Y2 +0.21, **Y3 −0.01 (weak last year)** |
| same, without 200 EMA filter | 1,247 | 38% | +0.06 | 1.11 | 1.4 | 200 EMA filter roughly **doubles** the edge |
| same rules on **random** stocks | 9,451 | 40% | −0.01 to −0.03 | 0.91–0.98 | −0.9 to −3.5 | **Proves selection is the edge** |
| 5-min ORB, in play, 10% ATR stop, EOD (Sep–Nov 2026, 45 days) | 578 | 17% | +0.10 | 1.11 | 0.8 | Matches Zarattini's profile; too few days to be significant |
| + SPY-above-200-EMA regime filter | 397 | 37% | +0.10 | 1.17 | 1.2 | **Did not help** → not used as a filter (regime used for sizing only) |

Rough money translation: +0.13R × ~230 trades/yr at **0.5% risk per trade** → about **+15%/yr** with a worst drawdown of ~43R ≈ **−20%**.
This is a simulation on a 145-stock large/mid-cap list using Yahoo data (hourly bars approximate the 5-min rules). **Verdict: average-to-good → USE IT.**

### Strategies TESTED and REJECTED
| Strategy | Exact rules tested | Result |
|---|---|---|
| VWAP / 21-EMA pullback | 10:00–14:30, price > VWAP and 9 EMA > 21 EMA, candle dips to the 21 EMA and closes back above; stop below the candle low/VWAP; target 2R | −0.03R (with ADX > 25: −0.02R) → **dropped** |
| VWAP 2σ mean reversion | 10:30–15:00, close beyond VWAP ± 2σ and RSI(14) > 75 / < 25; target VWAP; stop beyond the day's extreme | −0.27R → **dropped** |
| ORB-15m, stop at the middle of the range | First 3 candles, 2R target or EOD | −0.12R → **dropped** |
| ORB with stop at the opposite side of the range | 5-min OR | −0.05 to −0.09R → **dropped** (stop too wide, kills R) |
| Previous-day high/low break | 10:00–14:30, close through PDH/PDL with volume > 1.5× average; stop 0.15 ATR beyond the level; target 2R | +0.05R but **only 29 trades** → **watch list**, not live |

### What this changes in the earlier design
- **Confluence score (Module 3)** becomes **hard rules**: in play + candle direction + 200 EMA side. All three are required, no points system.
- **Daily regime (HMM)** → used for **position size** only (High-Vol = half size), not as an entry filter. The SPY filter didn't help.
- **Intraday regime / ADX** → not used for ORB (no improvement in tests).
- **Analyst bias** (macro/sentiment LONG/SHORT) → untested (no historical sentiment). For now it only **ranks/excludes** candidates; the first-candle direction decides the side.

## 6. Daily Timeline
```
WEEKLY          PRE-MARKET                 OPEN (+5 min)        MARKET HOURS                      POST-MARKET
Fundamental  →  Macro, Regime,          →  Stocks in Play,   →  Trading Agent loop:            →  Journal, expectancy,
screen          Sentiment (candidates)     Direction & Rank     200 EMA → strategy → score →      lessons → back to Agent 1
                                           (top 10–20)          risk → execute → monitor
                                                                         ↓
                                                                   📊 DASHBOARD
```

## 7. Dashboard (what judges see)
- Analyst reasoning: macro picture, regime, top picks with explanations
- Trader live view: setups found, scores, trades taken/skipped + why
- Open positions, P&L, equity curve vs. SPY buy-and-hold
- Expectancy & stats; "our picks vs. random" comparison

## 8. Improvements we add beyond TradingAgents / my additions
1. Regime-gated strategy selection and position sizing (TradingAgents has no regime)
2. Structured JSON (Pydantic) between agents instead of long text reports
3. Deterministic risk + execution (LLM can't override limits)
4. Portfolio-level view (watchlist, exposure, sector limits) — TradingAgents is single-ticker
5. Regime-tagged lessons
6. Event-day guard (FOMC/CPI/NFP)
7. Point-in-time macro data (ALFRED) → no look-ahead bias
8. Sector tilt from macro
9. Market breadth + sector strength in regime check
10. Hype detection (contrarian social signal)
11. Confluence scoring
12. Trailing stops + regime-exit in monitor
13. "Our picks vs. random" alpha proof
14. Costs (slippage + fees) always modeled

## 9. Tentative Tech Stack (not finalized — architecture phase pending)
| Part | Choice |
|---|---|
| Language | Python |
| Orchestration | LangGraph (same as TradingAgents) or plain Python loop |
| LLMs | **Provider-agnostic** (decided 2026-11-23, after the user asked about Gemini): a single `llm` client in `luma/core/` with Gemini / Claude / others behind it, chosen in config. Light tasks (sentiment, post screening) → a fast/cheap model (Gemini Flash or Claude Haiku); explanations and lessons → a stronger model (Gemini Pro or Claude Sonnet). Structured JSON output is required (Gemini `response_schema`, Claude tool-use). |
| Regime | `hmmlearn` |
| Indicators/patterns | `pandas-ta` + custom detectors |
| Data | yfinance (prices, intraday 5-min ~60 days), FRED/ALFRED (macro), news API, Reddit API, StockTwits |
| Broker | Own simulated broker (default) + optional Alpaca paper |
| Storage | SQLite |
| Schemas | Pydantic |
| UI | Streamlit |
| Config | `MARKET = "US"` (later `"IN"`): open time, universe, macro series, broker |

## 9A. ARCHITECTURE v1 (drafted 2026-11-23, not built yet)
**Diagram:** `docs/architecture.html` · published (private) at https://claude.ai/artifact/YZfmVycjozrkyN1phqh5Nj

**Principle:** the same Trader code runs live and in backtests (only the clock and broker are swapped). The LLM never sits in the order path.

**Layers (top → bottom):**
1. **Data adapters** (`data/`): Yahoo/Alpaca bars (daily, 5-min, live), FRED/ALFRED, news, Reddit, StockTwits, economic + earnings
   calendar. Every call goes through a cache, plus an **as-of date guard** (no look-ahead).
2. **Orchestrator + clock** (plain Python + APScheduler, US/Eastern): Sun 18:00 weekly → 08:00 pre-market → 09:35 picks →
   loop every 5 min 09:35–15:55 → 16:15 post-market. In backtest mode a replay clock drives the same jobs.
3. **Agent 1 Analyst:** M1 Fundamental (code) → M2 Macro (code score + LLM narrative) → M3 Regime (HMM code + LLM explanation) →
   M4 Sentiment (LLM scores headlines/posts into a structured band/score/confidence) → M5 Stocks in Play (code: RVOL) →
   M6 Rank (code score + LLM "why" text) → **Watchlist** (Pydantic JSON, saved to DB).
4. **Agent 2 Trader:** Signal engine (ORB rulebook 5A) → Rule gate (in play + candle color + 200 EMA side) → **Risk manager (code)** →
   **Execution** (SimBroker | Alpaca paper, same interface) → Monitor (stops, EOD flatten at 15:55) → Journal & Lessons
   (expectancy, vs-random, LLM reflection) → **lessons feed back into Agent 1**.
5. **Storage:** SQLite tables: universe, fundamentals, macro_snapshots, regimes, sentiment, watchlists, signals, orders, fills,
   positions, trades, equity, lessons, llm_calls (audit log).
6. **Dashboard** (Streamlit, read-only on SQLite): Analyst view, Trader live view, P&L vs SPY, stats, picks vs random.
7. **Backtest harness:** replays historical bars through the same Agent 2 code with the SimBroker and costs.

**LLM use (Claude):** Haiku: sentiment scoring, post screening. Sonnet: macro/regime/rank explanations, daily lessons.
Every LLM output is a Pydantic schema; on failure the module falls back to the deterministic score (the system still trades).

**Proposed folders:** `config/` (settings, market_us) · `luma/core/` (schemas, db, clock, llm) · `luma/data/` · `luma/agents/analyst/` (6 modules) ·
`luma/agents/trader/` (signals, gate, risk, broker, monitor, journal) · `luma/orchestrator/` · `luma/backtest/` · `dashboard/` · `tests/`.

### 9B. Tool checklist (checked on the user's PC, 2026-11-23)
- **Installed:** Python 3.13.7, pip, git 2.51, VS Code, Node 24. Python libraries: pandas, numpy, scipy, scikit-learn, yfinance, pydantic,
  python-dotenv, PyYAML, pandas-ta, streamlit, plotly, SQLAlchemy, alpaca-py, requests, pytest.
- **To install:** apscheduler, hmmlearn, fredapi, praw (Reddit), google-genai (Gemini), anthropic (optional), ruff.
  Use a virtual env (`.venv`) for the project.
- **Accounts / keys (user):** Gemini API key (Google AI Studio), FRED API key, Reddit app (client id/secret), news API key
  (e.g. Finnhub / NewsAPI free tier, to pick), optional Alpaca paper keys, GitHub repo for the team. StockTwits public endpoint (no key, rate-limited).

### 9C. Hackathon sponsor stack (given 2026-11-23, NOT decided yet)
The hackathon lists 5 tools we must use. They are agent infrastructure, **not LLMs**, so Gemini/Claude are still needed.
| Tool | What it is (from web search; mostly vendor claims) | What it would replace in our design |
|---|---|---|
| **BAND** | Multi-agent chat rooms: agents message each other, hand off tasks, keep context across sessions; desktop app shows who owns what. Built mainly for coding agents (Claude Code, Codex). | The Analyst→Trader `watchlist.json` hand-off and the lessons feedback (now a DB table). Adds "team visibility" for the demo. |
| **AdaL** (SylphAI) | Terminal coding agent / agent harness (npm `@sylphai/adal-cli`), works with Claude/Gemini/GPT, has an SDK + headless mode. | Our hand-written agent loop (role prompt + tools + memory) for each agent — or just used as the dev tool to build the code. |
| **Finch** (FinChip + AgentOn) | Marketplace that packages AI skills as reusable "Chips" + an agent task-dispatch network. Little public detail. | The module/tool layer: M1–M6 and T1–T6 packaged as reusable skills. |
| **Lyzr** | Enterprise agent platform: orchestration, guardrails, access control, action logs, model-agnostic. | The orchestrator (plain Python/LangGraph), the `llm_calls` audit log, and the "LLM can't touch money" governance story. |
| **Agent37** | Persistent isolated cloud sandboxes for agents (gVisor), files + memory survive restarts, billed while running (YC F26). | Running on a laptop: each agent gets its own always-on sandbox so the 08:00→16:15 schedule runs unattended. |
**Must stay our own code regardless:** data adapters, ORB rulebook (5A), risk manager, broker/execution, trade DB, backtest, dashboard.
**Open:** are all 5 mandatory or pick some? (ask organizers)

## 10. Known Risks / Caveats
- ORB needs intraday data; free 5-min data ≈ last 60 days → limited long backtests.
- Market open: US 9:30 ET (India 9:15 IST if added later).
- Paper fills are optimistic (slippage/liquidity).
- ORB edge vanishes without good stock selection and after costs (index replication).
- Regime models overfit — validate out-of-sample.
- Historical social sentiment is hard to obtain → mostly live.
- Reference projects are "research only, not financial advice" → present ours as a simulation.
- Check licenses before borrowing any code (TradingAgents = Apache-2.0).

## 11. OPEN QUESTIONS (answer these next)
1. **Final list size:** top **10** or top **20** stocks per day?
2. **Holding period:** intraday only (flatten EOD, like the paper) or also swing trades?
3. **Claude API key:** does the team have one?
4. **Deadline / time available** and team size?
5. Organizer confirmation: US paper trading OK? Internal modules don't count as agents?
6. **Risk rules vs. ORB (new, 2026-11-23):** ORB wins only ~17–40% of trades and takes up to 20 stocks/day. The old rules
   ("max 5 positions", "stop at −2% daily loss") would cut it off on normal losing streaks. Proposal: **0.25–0.5% risk per trade,
   up to 20 positions, daily loss stop −3%, max 4× leverage**. Needs a decision.

## 12. Next Steps
1. Answer open questions (Section 11).
2. Finalize project definition.
3. Design the architecture (folders, state schemas, orchestration, data flow).
4. Build in phases: (1) core end-to-end on one ticker → (2) full Analyst modules → (3) journal/backtest/metrics → (4) dashboard + demo.

## 12a. Session Log
- **2026-11-23 (session 1):** Defined the project: research, the 2-agent design, all modules (Sections 0–11).
- **2026-11-23 (session 2):** Resumed from this file. User asked for every conversation to be saved here
  as it happens. No new project decisions yet; the open questions in Section 11 are still waiting for answers.
- **2026-11-23 (session 3):** User asked which S&P 500 conditions (VIX, pre-market move > 100 pts) make ORB fail, so
  those days can be skipped. Ran the study (Section 2.4). Result: VIX level and big gaps are not reliable filters; a
  VIX spike > 10% the day before is the only consistent warning. Next: rerun on 5/15-min ORB once 1-min data (Alpaca) is available.
- **2026-11-23 (session 3, cont.):** User asked for a deeper study.
  - **Setup:** 30-min ORB. Entry on the first 5-min candle that closes outside the range. 9 stop/target schemes. Goal: find
    indicators that predict the whipsaw pattern (breaks one side, then closes beyond the other side, then chops).
  - **Built:** `scripts/orb30_engine.py` (about 50 indicators), `scripts/analyze_orb30.py` (per-year consistency check plus a
    walk-forward model) and `scripts/dl_alpaca.py`.
  - **Literature review:** dealer gamma (GEX) and SPY 5-day RSI (Baltussen 2021; Zarattini 2024); NR4/NR7 means more follow-through;
    opening-range relative volume; Dalton's open types.
  - **Data:** GEX data downloaded (SqueezeMetrics DIX.csv). Free 1-min sources (Dukascopy, HistData) were blocked.
  - **Blocked:** user chose to create Alpaca paper API keys. Only the 60-day test (38 trades) has run so far.
- **2026-11-23 (session 3, cont. 2):** User said: no code, no setup steps, just give a plain summary (to pass on to others).
  - **Test run:** 3 years of hourly SPY (Dec 2023 to Nov 2026, 620 trades): 60-min opening range, entry on a candle close outside it,
    about 40 indicators.
  - **Result:** no exit scheme has a real edge. The best (stop at range middle, 2R target) made only +0.04R per trade.
  - **Whipsaw predictor 1:** a narrow opening range (< 0.7× its 20-day average) gave 2–4× more whipsaws in every year (23/17/8% vs 8/11/2%).
  - **Whipsaw predictor 2:** VIX < 15 lost money in all 3 years with the 2R exit.
  - **Combined skip rule (narrow range OR VIX < 15):** skipped days were worse in all 3 years, but the trades kept are still about breakeven.
  - **No help:** ADX, events, NR7, inside day, weekday, gap.
  - **Walk-forward model:** worked in Y1 (AUC 0.65) but not in Y2 (AUC 0.50–0.55).
  - **Conclusion:** the filters cut losing days but do not make SPY ORB profitable; keep ORB for stocks in play.
    Results are in `research/orb_failure_days/results/orb60_hourly_report.txt`.

- **2026-11-23 (session 4):** User: "no entry/exit/stop rules defined; create and backtest them, use whatever is average or better."
  - Asked how the regime is detected during the day → two-layer regime proposed (Section 4, Module 3).
  - **Data:** Yahoo, 145 stocks. 5-min bars (Sep–Nov 2026, 45 tradable days) and hourly bars (Jan 2024–Nov 2026, 703 days).
  - **Tested:** 5 strategies × several stop/target variants, in play vs. random stocks.
  - **Result:** only ORB on stocks in play + 200 EMA works (+0.13R/trade, PF 1.24); the same rules on random stocks lose.
    The full rulebook is in **Section 5A**. Scripts are in the session scratchpad (temporary); every number is recorded in 5A.
  - **New open question #6:** the risk rules need adjusting to fit ORB.

- **2026-11-23 (session 4, cont.):** User asked to check TradingAgents' strategies (to copy them if they're good). Code
  read at commit 9fa1196 (Nov 2026). **Verdict: there is NO rule-based strategy to copy.**
  - **How it decides:** analysts (market/news/sentiment/fundamentals) write reports. The market analyst lets the LLM *pick* up to 8
    indicators (50/200 SMA, 10 EMA, MACD, RSI, Bollinger, ATR, VWMA), with no fixed thresholds. Bull and Bear researchers debate,
    the Research Manager rates (Buy/Overweight/Hold/Underweight/Sell), the Trader LLM outputs Buy/Hold/Sell with an *optional*
    entry and stop price that it invents itself, three risk debaters argue, and the Portfolio Manager gives the final rating.
  - **No** entry trigger, exit rule, take-profit, timeframe, position-sizing formula, or order execution.
    The default config does 1 debate round, daily data, one ticker per run.
  - **Their "backtest"** scores only the rating's direction: a 5-trading-day hold from the next close vs. SPY.
    It is not a P&L simulation, and the README says the results are not replicable.
  - **Worth reusing (ideas, Apache-2.0):** Pydantic structured outputs (rating, entry/stop, sentiment band + 0–10 score + confidence);
    a "verified market snapshot" tool so the LLM can't invent numbers; point-in-time data guards against look-ahead;
    a memory log that settles each decision after N days, computes alpha vs. SPY, and writes an LLM reflection;
    social-post relevance screening.
  - **Decision:** keep our backtested ORB rulebook (5A) as the trading core. Borrow only the items above for Agent 1 and the Journal.
- **2026-11-23 (session 4, cont. 2):** User asked for a proper architecture diagram (design only, nothing built). Drafted
  **Section 9A Architecture v1** and an HTML diagram page. User asked to save everything so far → saved.
  Still open: Q6 (risk rules for ORB), plus Q1–Q5.
- **2026-11-23 (session 4, cont. 3):** The user can use the Gemini API, so the LLM layer is now provider-agnostic (Section 9).
  The user asked whether I can build the system myself (answer: yes, except API keys, decisions, and live-market testing).
  The user asked for the full build prompt for the architecture first, to review before building.
  Written: `docs/BUILD_PROMPT_PHASE0.md` (skeleton on fake data, with defaults for the open decisions and a review checklist). **Not started building.**
- **2026-11-23 (session 4, cont. 4):** The user made an architecture diagram in an external tool (`image.png`, `image copy.png`). Review: the boxes are
  right, but the diagram was missing the Analyst→Trader watchlist hand-off, Trader→data, the lessons loop, the data layer and the backtest runner,
  had too few data sources, and had a wrong Data↔Broker line. Corrected diagram prompt: `docs/DIAGRAM_PROMPT.md`.
- **2026-11-23 (session 4, cont. 5):** Checked v2 (`architecture-a3-1795446644778.pdf`): ~85% right. All 5 layers and boxes are present, and the
  Data↔Broker line is gone. Remaining issues: orders are routed through Data Adapters instead of Trader→Broker; Backtest Runner points to Analyst instead of Trader;
  the Analyst↔Trader arrows have no labels (watchlist / lessons); most labels are missing; module lists are cut off; the "No LLM in T1–T5" note, legend and title are missing.
- **2026-11-23 (session 4, cont. 6):** Checked v3 (`architecture-a3-1795447670704.pdf`): ~88%. New labels are there (save results, lessons, T6 journal only,
  live 5-min bars) and the Trader modules are listed. NOT fixed: orders still go through Data Adapters→Broker; Backtest→Analyst (should go to Trader);
  no "watchlist.json" hand-off label; the lessons arrow points the wrong way (Analyst→Trader); the Analyst module list is cut off at M5; no "No LLM" note, legend or title.
  Advice: fix these 4 arrows by hand in the tool.
- **2026-11-23 (session 5):** User asked for a recap of progress so far. Summary given; no new decisions. Note: `research/` and
  `scripts/` folders mentioned above are not in `luma/` (backtest scripts lived in old session scratchpads).
  Updated the architecture diagram's LLM section to provider-agnostic (Gemini/Claude tiers), republished.
  User shared the required hackathon stack (BAND, AdaL, Finch, Lyzr, Agent37) → researched and mapped in Section 9C.
  Rewrote `docs/DIAGRAM_PROMPT.md` as the complete v4 prompt with the sponsor stack: Lyzr = orchestrator + LLM gateway/audit,
  BAND = agent hand-off room (watchlist + lessons), Finch = skills registry, AdaL = harness inside each agent, Agent37 = one sandbox per agent.
  Orders still go Trader → Broker directly (no sponsor tool in the order path).
- **2026-11-23 (session 5, cont.):** Checked v4 diagram (`a.pdf`, built from the new prompt): all 6 layers and all boxes present, but
  the agent cards have no module lists / AdaL harness, the "No LLM" note, title, legend and sponsor badges are missing, box names are cut off,
  and several arrows are wrong (orders still drawn via Data Adapters→Broker; LLM Provider→Backtest Runner and →Market Clock; Broker→DB;
  watchlist label hidden). Too tangled to trace every line. Suggested: generate the diagram ourselves (HTML/SVG) from the prompt instead.
  User chose to keep the tool and asked for better arrows → wrote `docs/DIAGRAM_FIX_PROMPT.md`: fixed 5×4 grid layout, 6 colour-coded
  arrow types (hand-off/control/LLM/data/DB/orders), orthogonal routing rules, exactly 24 arrows, explicit delete list.
- **2026-11-23 (session 5, cont. 2):** Checked v5 (`Downloads/architecture-a2-1795455405283.pdf`). Better: module lists + AdaL harness
  now in agent cards, Broker has a single "orders (T4)" input, Data Adapters→Broker gone, LLM→Clock gone. Still wrong: tool ignored the grid
  and colour coding (all amber), no title/legend/No-LLM note/sandbox boundaries; "[Sponsor]" text put on User/Analyst/Trader names;
  labels swapped ("guarded + logged" on Data Adapters→Data Sources, "fetch" on Backtest→LLM); names truncated; labels overlap.
  Gave a short fix-list prompt; recommended building the diagram ourselves in HTML if the tool can't do colours.
  User: must use the design tool, no colours needed, just make arrows visible → `docs/DIAGRAM_ARROWS_PROMPT.md`
  (thicker lines, big arrowheads, solid vs dashed only, spacing, no lines through boxes, line jumps, label placement, 3 label fixes).
  Then wrote `docs/DIAGRAM_CONTENT_PROMPT.md` for the non-arrow fixes (names, sponsor tags, full module lists, No-LLM note,
  Agent37 sandbox boxes, title). Use: arrows prompt first, then content prompt.
- **2026-11-23 (session 5, cont. 3):** Checked v6 (`luma/b.pdf`). Content better (sponsor tags right, User/Analyst/Trader renamed,
  Agent37 sandbox boxes added). Not correct yet: the tool moved boxes into a scattered diagonal (agents top-left, UI bottom-right), so lines are
  longer and cross more; module lists still cut after M1/T1; no No-LLM note, title or legend; Lyzr name still cut; Trader→Broker is a long
  detour. Advice: drag boxes by hand into the 5-row layout, then let the tool re-route.
- **2026-11-23 (session 5, cont. 4):** User asked for one complete rebuild prompt tuned to how the tool behaves, plus an explanation of every part.
  Wrote `docs/DIAGRAM_REBUILD_PROMPT.md`. Tool lessons applied: it lays groups out as left-to-right columns, cuts long names and long
  descriptions, shows tags in full, and copies any instruction text inside a box. So: 5 columns (UI → Platform → Agents → Data/Execution →
  External), short names, modules as tags, Sponsor as a tag, BAND Room placed BETWEEN the two agents, Broker beside the Trader, 22 arrows.
  Design simplification: agents call the LLM Provider directly (Lyzr guardrails shown as a tag), BAND Room→Desktop arrow dropped.
- **2026-11-23 (session 5, cont. 5):** Checked v7 (`luma/c.pdf`, from the rebuild prompt). Layout finally right (5 columns, BAND Room
  between the agents, Trader→Broker short, Data Adapters→Data Sources "fetch"). Remaining before submit: DB/Data Adapters targets swapped
  ("market and news data" + "live 5-min bars" end at Luma DB; save picks → LLM Provider, save trades → Data Sources); stale labels
  ("LLM calls: T6 lessons only", "reads results"); extra BAND Desktop→Lyzr line; module tags, No-LLM tag, title, legend missing; labels
  overlap the Analyst tags and Market Clock text. Gave a final fix prompt.
- **2026-11-23 (session 5, cont. 6):** Name ideas given (Alpha Duo, TwinEdge, Scout & Strike [recommended], OpenRange, PlayMaker, keep Luma);
  user hasn't chosen. Wrote the submission solution summary: `docs/SOLUTION_SUMMARY.md` (uses "Luma" until a name is chosen).
- **2026-11-23 (session 5, cont. 7):** Architecture Copilot requires a PRD before submitting. Wrote `docs/PRD.md` (goals, users, stories,
  functional reqs A1–A7 / T1–T6 / P1–P7 / D1–D4, non-functional, data, metrics, backtest evidence, risks, milestones, open questions).
  Uses the proposed Q6 risk settings as defaults (0.25–0.5%/trade, 20 positions, −3% daily stop, 4× leverage) — still to confirm.
- **2026-11-24 (session 5, cont. 8):** **DECISION: project name = OpenRange** (after the Opening Range Breakout strategy). Renamed "Luma" →
  "OpenRange" in all submission docs (PRD, PRD prompt, solution summary, diagram prompts) and the architecture page title. Folder/package
  names (`luma/`) left unchanged. Gave the PRD prompt for Architecture Copilot's in-session PRD and a ~200-word solution summary.
- **2026-11-24 (session 5, cont. 9): BUILD STARTED — Phase 0 done.** Python package `openrange/` (in the `luma/` folder), venv `.venv`.
  - Built per `docs/BUILD_PROMPT_PHASE0.md`: core (schemas, config, db, clock, llm, indicators), data adapters with as-of guard +
    deterministic fake data, Analyst M1–M6, Trader T1–T6, platform/bus.py (LocalBus; BandBus stub), platform/skills.py (Finch
    catalogue), orchestrator (wiring, jobs/run_day, APScheduler live scheduler), backtest runner, Streamlit dashboard, README.
  - Already real logic (not stubs): Piotroski, macro scoring, rule-based regime (HMM in Phase 2), sentiment blend, RVOL, ORB
    signals, rule gate, risk sizing/limits, SimBroker with costs, flatten, journal stats. Only the DATA is fake.
  - Defaults used for open Q6: 0.5% risk/trade, 20 positions, 2 per sector, −3% daily stop, 4× leverage (config/settings.yaml).
  - Debug found + fixed: SimBroker same-bar rule always assumed stop after entry (22/23 trades stopped). Now uses OHLC path
    (green O→L→H→C, red O→H→L→C). 30-day fake backtest: 50 trades, 4 wins (best +7.4R), 46 stops — ORB profile; fake data has no edge.
  - Checks: pytest 38/38 green, ruff clean, fake day runs end to end, dashboard renders 4 tabs with no errors.
  - User stressed: ALL 5 sponsor tools (BAND, AdaL, Finch, Lyzr, Agent37) must be used or the project is not evaluated.
    Research on their real APIs started. Next: Phase 1 (real Yahoo data) + sponsor integration.
- **2026-11-24 (session 5, cont. 10): Sponsor tools integrated (code), Phase 4 code done.** Research findings + how each is used:
  - **BAND** (`platform/bus.py` BandBus): REST Agent API; each agent = its own "remote agent"; messages
    `@Other [openrange:<topic>] {json}` in one room; pulls via `GET /messages/next`. Reply shape of /next unverified.
  - **Lyzr** (`platform/lyzr.py`): Analyst LLM provider via `POST /v3/inference/chat/` (x-api-key, agent_id per tier)
    → guardrails + audit log. SuperFlow cron is UI-only, so our APScheduler stays the clock.
  - **AdaL** (`platform/adal.py`): Trader T6 review via headless CLI `adal -q ... -o json --system-prompt-file`,
    session resumed daily = memory; personality `agents_harness/*/SYSTEM.md`; 12 skills `.adal/skills/`; `AGENTS.md`.
  - **Finch** (`platform/skills.py`, `platform/finch.py`): 12 skill packages in `skills/` (SKILL.md + skill.json);
    public market search works live (50 results for "trading"). Publishing needs wallet login + CLI (manual; format not public).
  - **Agent37** (`Dockerfile`, `platform/agent37.py`): one sandbox per agent, scheduler `--role analyst|trader`;
    REST create instance + exec. Must disable auto-sleep. Docker build not tested locally.
  - Config: `platform:` section in settings.yaml (bus, analyst_llm, trader_llm, per-tool ids); keys in .env.
    Missing keys → automatic fallback to local + warning. Guide: `docs/SPONSOR_SETUP.md`. Dashboard sidebar shows status.
  - Checks: pytest 46/46 (8 new platform tests with mocked HTTP), ruff clean, fake day + dashboard OK.
  - Blocked on user: accounts/keys for BAND, Lyzr, AdaL login, Finch wallet, Agent37 credit.
- **2026-11-24 (session 5, cont. 11): Phase 1 — real Yahoo prices.**
  - `openrange/data/yahoo.py` (download + adapter, cache in data/cache/yahoo, 5-min history grows on each refresh),
    `config/universe_us.yaml` (147 stocks; SQ/X dropped, ROKU daily data broken, CEG no 5-min), `settings: data: fake|yahoo`,
    `analyst.filters` (Piotroski + sentiment veto OFF in real-data backtests while those sources are fake),
    `--selection random` baseline, `--stop-atr`, `openrange/backtest/report.py`. `.env` created (empty) for the user.
  - Bugs fixed: YAML read ticker ON as True (all tickers now quoted); <200 days history crashed M3/M6; empty Yahoo file crashed;
    download used fake universe; risk sizing let the first 2–3 orders eat all 4x leverage (201 of 473 signals got 0 shares)
    → new per-position cap = 4 x equity / 20 = $20k.
  - **Real result (Sep 21 – Nov 20 2026, 44 days, 10% ATR stop, before sizing fix):** our picks 183 trades, win 10.9%,
    **−0.42R** (t −2.5); random stocks 168 trades, win 17.3%, −0.14R (t −0.8). Picks did WORSE than random.
  - Diagnosis (verified one trade by hand vs raw bars, engine correct): 10%-ATR stop (e.g. SOFI $0.066) is smaller than one
    5-min bar's range on in-play stocks; 34% of stops happen inside the entry bar, where 5-min data can't tell the order of
    entry vs stop. The Zarattini rule needs **1-minute data (Alpaca)** to be measured honestly. Testing 25% ATR stop
    (measurable on 5-min bars; the hourly study used 25%) for picks and random.
  - User is getting Alpaca paper keys (needed for 1-min history + paper trading).

## 13. Sources
- TradingAgents: https://github.com/TauricResearch/TradingAgents · paper https://arxiv.org/abs/2412.20138
- ai-hedge-fund: https://github.com/virattt/ai-hedge-fund
- AgenticTrading: https://github.com/Open-Finance-Lab/AgenticTrading
- Quorai: https://quorai.github.io/
- ai-native-hedge-fund: https://github.com/td-02/ai-native-hedge-fund
- market-regime-detection: https://github.com/Sakeeb91/market-regime-detection
- Zarattini/Barbon/Aziz ORB Stocks in Play: https://concretumgroup.com/a-profitable-day-trading-strategy-for-the-u-s-equity-market/
- Can Day Trading Really Be Profitable?: https://papers.ssrn.com/abstract=4416622
- QuantConnect replication: https://www.quantconnect.com/research/18444/opening-range-breakout-for-stocks-in-play/
- ORB on indices net-zero: https://www.mql5.com/en/blogs/post/776235
- LLM news + momentum: https://arxiv.org/html/2510.26228v1
- AI attractiveness scores: https://arxiv.org/pdf/2601.11958
- MarketSenseAI: https://arxiv.org/pdf/2401.03737v1
- LLM strategy finding: https://arxiv.org/html/2409.06289v4
- NYU Shanghai thesis: https://cdn.shanghai.nyu.edu/sites/default/files/ruilin_wu_thesis_nyush_honors_2026.pdf
- Market Regime Council: https://arxiv.org/pdf/2605.24490
- Miyazaki et al.: https://arxiv.org/html/2602.23330
- Agent4Crypto: https://arxiv.org/pdf/2611.12269
- Inside the Trading Loop: https://arxiv.org/pdf/2611.11657
- Alpaca paper trading: https://alpaca.markets/learn/start-paper-trading
- Alpaca hackathon: https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon
- QuestDB HMM regime: https://questdb.com/glossary/market-regime-detection-using-hidden-markov-models/
