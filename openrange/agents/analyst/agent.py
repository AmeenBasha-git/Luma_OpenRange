"""Analyst Agent: decides WHAT to trade and in WHICH direction.

Three entry points, called by the orchestrator:
    run_weekly(as_of)     M1 fundamentals                      -> quality list
    run_premarket(as_of)  M2 macro, M3 regime, M4 sentiment     -> candidates
    run_open(as_of)       M5 stocks in play, M6 rank            -> Watchlist (published to the bus)
"""

from __future__ import annotations

from datetime import datetime

from openrange.agents.analyst import m1_fundamental, m2_macro, m3_regime, m4_sentiment, m5_in_play, m6_rank
from openrange.core.config import Settings
from openrange.core.db import Database
from openrange.core.llm import LLMClient
from openrange.core.log import get_logger
from openrange.core.schemas import (
    FundamentalScore,
    Lesson,
    MacroSnapshot,
    RegimeState,
    SentimentScore,
    Watchlist,
)
from openrange.data.hub import DataHub
from openrange.platform.bus import MessageBus, Topic

log = get_logger(__name__)


class AnalystAgent:
    def __init__(self, settings: Settings, data: DataHub, llm: LLMClient, db: Database, bus: MessageBus):
        self.settings = settings
        self.data = data
        self.llm = llm
        self.db = db
        self.bus = bus
        self.universe = settings.market.universe
        self.sectors = {s.symbol: s.sector for s in self.universe}

        # State built up during the week / day
        self.fundamentals: dict[str, FundamentalScore] = {}
        self.macro: MacroSnapshot | None = None
        self.regime: RegimeState | None = None
        self.sentiment: dict[str, SentimentScore] = {}
        self.candidates: list[str] = []
        self.lessons: list[Lesson] = []

    # ------------------------------------------------------------ weekly

    def run_weekly(self, as_of: datetime) -> list[FundamentalScore]:
        s = self.settings
        scores = m1_fundamental.run(
            self.universe, self.data, as_of, min_piotroski=s.analyst.min_piotroski,
            min_price=s.strategy.min_price, min_avg_volume=s.strategy.min_avg_volume, min_atr=s.strategy.min_atr,
            use_piotroski=s.analyst.filters.piotroski,
        )
        self.fundamentals = {f.symbol: f for f in scores}
        self.db.save_many("fundamentals", scores, as_of, symbol_field="symbol")
        log.info("M1 fundamentals: %d of %d passed", sum(f.passed for f in scores), len(scores))
        return scores

    # ------------------------------------------------------------ pre-market

    def run_premarket(self, as_of: datetime) -> list[str]:
        if not self.fundamentals:
            self.run_weekly(as_of)
        self.lessons = self._read_lessons()

        self.macro = m2_macro.run(self.data, self.llm, as_of)
        self.db.save("macro_snapshots", self.macro, as_of)

        self.regime = m3_regime.run(
            self.universe, self.data, self.llm, as_of,
            benchmark=self.settings.market.benchmark, high_vol_size_mult=self.settings.risk.high_vol_size_mult,
        )
        self.db.save("regimes", self.regime, as_of)

        self.candidates = [symbol for symbol, f in self.fundamentals.items() if f.passed]
        scores = m4_sentiment.run(self.candidates, self.data, self.llm, as_of, self.settings.analyst.stocktwits_weight)
        self.sentiment = {s.symbol: s for s in scores}
        self.db.save_many("sentiment", scores, as_of, symbol_field="symbol")

        log.info("Pre-market: macro %s (%+.2f), regime %s, %d candidates, %d lessons from last session",
                 self.macro.bias, self.macro.score, self.regime.label, len(self.candidates), len(self.lessons))
        return self.candidates

    # ------------------------------------------------------------ 09:35

    def run_open(self, as_of: datetime) -> Watchlist:
        if self.macro is None or self.regime is None:
            self.run_premarket(as_of)

        st = self.settings.strategy
        in_play = m5_in_play.run(self.candidates, self.data, as_of, st.min_rvol,
                                 selection=st.selection, random_count=st.max_picks)
        self.db.save_many("in_play", in_play, as_of, symbol_field="symbol")

        watchlist = m6_rank.run(
            in_play, self.sectors, self.fundamentals, self.sentiment, self.macro, self.regime,
            self.data, self.llm, as_of,
            max_picks=self.settings.strategy.max_picks, event_size_mult=self.settings.risk.event_day_size_mult,
            sentiment_veto=self.settings.analyst.filters.sentiment_veto,
        )
        self.db.save("watchlists", watchlist, as_of)
        self.bus.publish(Topic.WATCHLIST, watchlist, as_of)
        log.info("09:35 watchlist: %d in play -> %d picks published", len(in_play), len(watchlist.picks))
        return watchlist

    # ------------------------------------------------------------ helpers

    def _read_lessons(self) -> list[Lesson]:
        """Lessons the Trader sent back after the last session."""
        message = self.bus.latest(Topic.LESSONS)
        return [Lesson.model_validate(item) for item in message["lessons"]] if message else []
