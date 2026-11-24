"""Builds every component from the settings and connects them. The ONE place that decides which
implementation is used:

    data     fake | yahoo                                         (config: data)
    LLM      per agent: fake | gemini | claude | lyzr | adal     (config: platform.analyst_llm / trader_llm)
    bus      local | band                                         (config: platform.bus)
    broker   sim | alpaca_paper                                   (config: broker)

If a sponsor tool is switched on but its key/setup is missing, it falls back to the local version
and logs a warning, so the system always runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from openrange.agents.analyst.agent import AnalystAgent
from openrange.agents.trader.agent import TraderAgent
from openrange.agents.trader.t4_broker import AlpacaPaperBroker, Broker, SimBroker
from openrange.core.config import Settings
from openrange.core.db import Database
from openrange.core.llm import ClaudeClient, FakeLLM, GeminiClient, LLMClient, LLMError
from openrange.core.log import get_logger
from openrange.data.hub import DataHub, make_data_hub
from openrange.platform.bus import BandBus, LocalBus, MessageBus

log = get_logger(__name__)


@dataclass
class TradingSystem:
    settings: Settings
    db: Database
    data: DataHub
    analyst_llm: LLMClient
    trader_llm: LLMClient
    broker: Broker
    analyst: AnalystAgent
    trader: TraderAgent


def new_run_id(mode: str) -> str:
    return f"{mode}-{datetime.now():%Y%m%d-%H%M%S-%f}"


# ------------------------------------------------------------------ LLM per agent

def make_llm(provider: str, role: str, settings: Settings, db: Database) -> LLMClient:
    """role = 'analyst' or 'trader'. Falls back to FakeLLM if the provider can't start."""
    keys, models, platform = settings.secrets, settings.llm.models, settings.platform
    try:
        if provider == "gemini":
            return GeminiClient(keys.gemini_api_key, models["gemini"], db)
        if provider == "claude":
            return ClaudeClient(keys.anthropic_api_key, models["claude"], db)
        if provider == "lyzr":
            from openrange.platform.lyzr import LyzrClient
            return LyzrClient(keys.lyzr_api_key, platform.lyzr, db)
        if provider == "adal":
            from openrange.platform.adal import AdalClient
            return AdalClient(platform.adal, role, db)
    except (LLMError, ImportError) as exc:
        log.warning("%s LLM '%s' unavailable (%s): using FakeLLM", role, provider, exc)
    return FakeLLM(db=db)


# ------------------------------------------------------------------ bus per agent

def make_bus(role: str, settings: Settings, db: Database) -> MessageBus:
    local = LocalBus(db, share_across_runs=settings.mode != "backtest")
    if settings.platform.bus != "band" or settings.mode == "backtest":
        return local
    band, keys = settings.platform.band, settings.secrets
    me, other = ((band.analyst_agent_id, band.trader_agent_id) if role == "analyst"
                 else (band.trader_agent_id, band.analyst_agent_id))
    api_key = keys.band_analyst_api_key if role == "analyst" else keys.band_trader_api_key
    try:
        return BandBus(local, band, api_key, me=me, other=other)
    except ValueError as exc:
        log.warning("BAND unavailable for %s (%s): using LocalBus", role, exc)
        return local


# ------------------------------------------------------------------ whole system

def build_system(settings: Settings, *, run_id: str | None = None, data: DataHub | None = None,
                 llm: LLMClient | None = None) -> TradingSystem:
    """Pass `data` or `llm` to override the defaults (tests do this; `llm` is then used by both agents)."""
    db = Database(settings.db_path, run_id or new_run_id(settings.mode), settings.mode)
    data = data or make_data_hub(settings)

    if llm is not None:
        llm.db = db
        analyst_llm = trader_llm = llm
    else:
        analyst_llm = make_llm(settings.platform.analyst_llm, "analyst", settings, db)
        trader_llm = make_llm(settings.platform.trader_llm, "trader", settings, db)

    if settings.broker == "alpaca_paper":
        broker: Broker = AlpacaPaperBroker(settings.secrets.alpaca_key, settings.secrets.alpaca_secret)
    else:
        broker = SimBroker(settings.starting_equity, settings.costs)

    analyst = AnalystAgent(settings, data, analyst_llm, db, make_bus("analyst", settings, db))
    trader = TraderAgent(settings, data.prices, broker, trader_llm, db, make_bus("trader", settings, db))
    return TradingSystem(settings, db, data, analyst_llm, trader_llm, broker, analyst, trader)
