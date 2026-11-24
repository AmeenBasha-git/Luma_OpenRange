"""OpenRange dashboard (read-only, reads the SQLite database).

    python -m streamlit run dashboard/app.py

Tabs: Analyst | Trader | P&L | Stats
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from openrange.core.config import load_settings
from openrange.core.db import list_runs, read_table

st.set_page_config(page_title="OpenRange", layout="wide")
DB = load_settings().db_path

st.title("OpenRange: Two-Agent Trading System")
if not DB.exists():
    st.info("No data yet. Run:  python scripts/run_fake_day.py")
    st.stop()

runs = list_runs(DB)
if runs.empty:
    st.info("No finished runs yet. Run:  python scripts/run_fake_day.py")
    st.stop()
run_id = st.sidebar.selectbox("Run", runs["run_id"], format_func=lambda r: r)
st.sidebar.caption(f"Database: {DB}")

platform = load_settings().platform
st.sidebar.subheader("Sponsor tools")
st.sidebar.write(f"**BAND** agent bus: `{platform.bus}`")
st.sidebar.write(f"**Lyzr** Analyst LLM: `{platform.analyst_llm}`")
st.sidebar.write(f"**AdaL** Trader review: `{platform.trader_llm}`")
st.sidebar.write("**Finch** skills: 12 packaged (`skills/`)")
st.sidebar.write("**Agent37** hosting: `python -m openrange.platform.agent37 status`")


def table(name: str) -> pd.DataFrame:
    return read_table(DB, name, run_id)


analyst_tab, trader_tab, pnl_tab, stats_tab = st.tabs(["Analyst", "Trader", "P&L", "Stats"])

# ------------------------------------------------------------------ Analyst
with analyst_tab:
    macro, regime, watch = table("macro_snapshots"), table("regimes"), table("watchlists")
    left, right = st.columns(2)
    if not macro.empty:
        m = macro.iloc[-1]
        left.metric("Macro bias", m["bias"], f"score {m['score']:+.2f}")
        left.write(m["narrative"])
    if not regime.empty:
        r = regime.iloc[-1]
        right.metric("Regime", r["label"], f"size x{r['size_multiplier']}")
        right.write(r["explanation"])
    st.subheader("Watchlist (09:35)")
    if not watch.empty:
        picks = pd.DataFrame(watch.iloc[-1]["picks"])
        if picks.empty:
            st.write("No picks today.")
        else:
            st.dataframe(picks[["ticker", "bias", "rvol", "conviction", "above_ema200", "or_candle", "reason"]],
                         width="stretch", hide_index=True)

# ------------------------------------------------------------------ Trader
with trader_tab:
    gate, risk, trades = table("gate_decisions"), table("risk_decisions"), table("trades")
    st.subheader("Rule gate")
    if not gate.empty:
        st.dataframe(gate[["signal.ticker", "signal.side", "signal.entry_price", "signal.stop_price",
                           "passed", "failed_rules"]], width="stretch", hide_index=True)
    st.subheader("Risk decisions")
    if not risk.empty:
        st.dataframe(risk[["approved", "reason", "intent.ticker", "intent.qty"]],
                     width="stretch", hide_index=True)
    st.subheader("Closed trades")
    if trades.empty:
        st.write("No trades.")
    else:
        st.dataframe(trades[["ticker", "side", "qty", "entry_price", "exit_price", "pnl", "r_multiple",
                             "exit_reason"]], width="stretch", hide_index=True)

# ------------------------------------------------------------------ P&L
with pnl_tab:
    equity = table("equity_curve")
    if equity.empty:
        st.write("No equity data.")
    else:
        equity["ts"] = pd.to_datetime(equity["ts"], utc=True).dt.tz_convert("America/New_York")
        st.plotly_chart(px.line(equity, x="ts", y="equity", title="Equity"), width="stretch")
        st.caption("SPY comparison arrives in Phase 3 (real data).")

# ------------------------------------------------------------------ Stats
with stats_tab:
    reports = table("daily_reports")
    if not reports.empty:
        r = reports.iloc[-1]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Trades", int(r["n_trades"]))
        c2.metric("Win rate", f"{r['win_rate']:.0%}")
        c3.metric("Avg R", f"{r['avg_r']:+.2f}")
        c4.metric("P&L", f"${r['pnl']:,.2f}")
        st.subheader("Lessons for tomorrow")
        for lesson in r["lessons"]:
            st.write(f"- {lesson['text']}")
    llm_calls = table("llm_calls")
    st.subheader("LLM audit log")
    st.write(f"{len(llm_calls)} calls this run" if not llm_calls.empty else "No LLM calls.")
    if not llm_calls.empty:
        st.dataframe(llm_calls[["provider", "model", "schema", "ok", "latency_s"]],
                     width="stretch", hide_index=True)
