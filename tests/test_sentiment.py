"""M4 sentiment: tone, StockTwits blend, mention spike, hype warning, and the live-only ApeWisdom source."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from openrange.agents.analyst import m4_sentiment
from openrange.core.llm import FakeLLM
from openrange.data.hub import fake_data_hub
from openrange.data.news import Headline, NewsAdapter
from openrange.data.social import ApeWisdomSocialAdapter, SocialAdapter, SocialStats

TZ = ZoneInfo("America/New_York")
AS_OF = datetime(2026, 11, 20, 8, 0, tzinfo=TZ)


class OneHeadline(NewsAdapter):
    def headlines(self, symbol, as_of, hours=24):
        return [Headline(symbol=symbol, ts=as_of - timedelta(hours=1), source="t", title=f"{symbol} beats estimates")]


class Mentions(SocialAdapter):
    def __init__(self, now, before):
        self.now, self.before = now, before

    def stats(self, symbol, as_of):
        return SocialStats(symbol=symbol, reddit_mentions=self.now, reddit_mentions_baseline=self.before)


def hub(news=None, social=None):
    h = fake_data_hub()
    h.news = news or OneHeadline()
    h.social = social or Mentions(10, 10)
    return h


def test_tone_comes_from_the_llm_when_there_is_news():
    llm = FakeLLM(responses={"SentimentLLMOutput": {"band": "Bullish", "score": 7.5, "confidence": "high",
                                                    "catalyst": "earnings beat"}})
    s = m4_sentiment.score_one("AAA", hub(), llm, AS_OF, stocktwits_weight=0.15)
    assert s.score == 7.5 and s.catalyst == "earnings beat"       # no StockTwits data -> tone only


def test_no_news_and_no_posts_is_neutral():
    class NoNews(NewsAdapter):
        def headlines(self, symbol, as_of, hours=24):
            return []

    s = m4_sentiment.score_one("AAA", hub(news=NoNews()), FakeLLM(fail=True), AS_OF, 0.15)
    assert s.score == 5.0


def test_hype_warning_needs_a_spike_and_very_bullish_tone():
    hot = FakeLLM(responses={"SentimentLLMOutput": {"band": "Very Bullish", "score": 9, "confidence": "high"}})
    assert m4_sentiment.score_one("AAA", hub(social=Mentions(400, 50)), hot, AS_OF, 0.15).hype_warning
    assert not m4_sentiment.score_one("AAA", hub(social=Mentions(60, 50)), hot, AS_OF, 0.15).hype_warning


def test_tiny_baselines_do_not_create_fake_spikes():
    s = m4_sentiment.score_one("AAA", hub(social=Mentions(4, 1)), FakeLLM(), AS_OF, 0.15)
    assert s.mention_spike < 1.0                                   # 4 / max(1, 5)


def test_stocktwits_blends_in_when_available():
    social = SocialStats(symbol="AAA", reddit_mentions=1, reddit_mentions_baseline=1,
                         stocktwits_bullish=100, stocktwits_bearish=0)
    assert m4_sentiment.blend_stocktwits(5.0, social, 0.2) == 0.8 * 5 + 0.2 * 10


def test_apewisdom_returns_nothing_for_past_dates():
    adapter = ApeWisdomSocialAdapter()
    adapter._table, adapter._loaded_at = {"AAA": (500, 50)}, float("inf")
    past = datetime(2025, 1, 10, 8, 0, tzinfo=TZ)
    assert adapter.stats("AAA", past).reddit_mentions == 0           # live-only source: no look-ahead
    assert adapter.stats("AAA", datetime.now(TZ)).reddit_mentions == 500
