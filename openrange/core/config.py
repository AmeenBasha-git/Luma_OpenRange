"""Loads config/settings.yaml + config/market_<market>.yaml + .env into one typed Settings object."""

from __future__ import annotations

import os
from datetime import time
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

from openrange.core.schemas import StockInfo

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


LLMProvider = Literal["fake", "gemini", "claude", "lyzr", "adal"]


class LLMSettings(BaseModel):
    models: dict[str, dict[str, str]]


class BandSettings(BaseModel):
    base_url: str
    room_id: str
    analyst_agent_id: str
    trader_agent_id: str


class LyzrSettings(BaseModel):
    base_url: str
    fast_agent_id: str
    smart_agent_id: str


class AdalSettings(BaseModel):
    command: str
    timeout_s: int


class Agent37Settings(BaseModel):
    api_url: str
    exec_url: str
    template: str


class PlatformSettings(BaseModel):
    """Sponsor tools. Every switch has a local fallback."""

    bus: Literal["local", "band"]
    analyst_llm: LLMProvider
    trader_llm: LLMProvider
    band: BandSettings
    lyzr: LyzrSettings
    adal: AdalSettings
    agent37: Agent37Settings


class RiskSettings(BaseModel):
    risk_per_trade_pct: float
    max_positions: int
    max_per_sector: int
    daily_loss_stop_pct: float
    max_leverage: float
    high_vol_size_mult: float
    event_day_size_mult: float


class StrategySettings(BaseModel):
    name: str
    stop_atr_fraction: float
    min_rvol: float
    selection: Literal["rvol", "random"]
    max_picks: int
    min_price: float
    min_avg_volume: float
    min_atr: float


class CostSettings(BaseModel):
    commission_per_share: float
    slippage_per_share: float


class AnalystFilters(BaseModel):
    piotroski: bool
    sentiment_veto: bool


class AnalystSettings(BaseModel):
    min_piotroski: int
    filters: AnalystFilters
    stocktwits_weight: float


class SourceSettings(BaseModel):
    news: Literal["fake", "alpaca"]
    social: Literal["fake", "apewisdom"]


class SessionTimes(BaseModel):
    open: time
    or_end: time
    flatten: time
    close: time
    bar_minutes: int


class MarketSettings(BaseModel):
    timezone: str
    benchmark: str
    session: SessionTimes
    schedule: dict[str, str]
    universe: list[StockInfo]
    macro_series: dict[str, str]


class Secrets(BaseModel):
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    fred_api_key: str = ""
    news_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    alpaca_key: str = ""
    alpaca_secret: str = ""
    band_analyst_api_key: str = ""
    band_trader_api_key: str = ""
    lyzr_api_key: str = ""
    agent37_api_key: str = ""


class Settings(BaseModel):
    mode: Literal["fake", "backtest", "live"]
    data: Literal["fake", "yahoo", "alpaca"]
    sources: SourceSettings
    llm: LLMSettings
    platform: PlatformSettings
    broker: Literal["sim", "alpaca_paper"]
    starting_equity: float
    risk: RiskSettings
    strategy: StrategySettings
    costs: CostSettings
    analyst: AnalystSettings
    db_path: Path
    cache_dir: Path
    market: MarketSettings
    secrets: Secrets


def _read_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_settings(settings_file: Path | None = None, **overrides) -> Settings:
    """Read the YAML files and .env. Paths are resolved from the project root.
    `overrides` replace top-level keys of settings.yaml, e.g. load_settings(mode="backtest", data="yahoo")."""
    load_dotenv(PROJECT_ROOT / ".env")
    raw = _read_yaml(settings_file or CONFIG_DIR / "settings.yaml")
    raw.update(overrides)
    market = _read_yaml(CONFIG_DIR / f"market_{raw['market']}.yaml")
    if raw["data"] != "fake":                                   # real data -> real universe list
        market["universe"] = _read_yaml(CONFIG_DIR / f"universe_{raw['market']}.yaml")["universe"]

    secrets = Secrets(**{name: os.getenv(name.upper(), "") for name in Secrets.model_fields})

    return Settings(
        mode=raw["mode"],
        data=raw["data"],
        sources=raw["sources"],
        llm=raw["llm"],
        platform=raw["platform"],
        broker=raw["broker"],
        starting_equity=raw["account"]["starting_equity"],
        risk=raw["risk"],
        strategy=raw["strategy"],
        costs=raw["costs"],
        analyst=raw["analyst"],
        db_path=PROJECT_ROOT / raw["paths"]["db"],
        cache_dir=PROJECT_ROOT / raw["paths"]["cache"],
        market=market,
        secrets=secrets,
    )
