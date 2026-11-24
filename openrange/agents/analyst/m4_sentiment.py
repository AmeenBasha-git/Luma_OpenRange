"""M4 Sentiment (daily, pre-market) on the candidate stocks.

  tone score    = the LLM reads the news (headline + summary) and any Reddit posts -> 0..10
                  (keyword fallback if the LLM is unavailable)
  final score   = tone score, blended with StockTwits bull/bear tags when that source is available
  mention spike = Reddit mentions in the last 24h / the normal level (ApeWisdom)
  hype warning  = mentions jumped 3x or more AND the tone is very bullish (a contrarian warning sign)

Sources (config/settings.yaml -> sources): news = Alpaca News, social = ApeWisdom. Reddit API: future.
"""

from __future__ import annotations

from datetime import datetime

from openrange.core.llm import LLMClient, LLMError
from openrange.core.schemas import SentimentLLMOutput, SentimentScore
from openrange.data.hub import DataHub
from openrange.data.social import SocialStats

POSITIVE = ("beats", "raises", "upgrade", "new product", "record", "strong", "surges", "wins")
NEGATIVE = ("misses", "downgrade", "probe", "lawsuit", "cut", "weak", "falls", "recall")
HYPE_SPIKE = 3.0               # mentions at least 3x normal
HYPE_SCORE = 8.0               # and tone at least 8/10
MIN_BASELINE_MENTIONS = 5.0    # avoid huge "spikes" from 1 -> 4 mentions


def band_for(score: float) -> str:
    bands = [(8.5, "Very Bullish"), (7, "Bullish"), (5, "Slightly Bullish"),
             (3.5, "Slightly Bearish"), (2, "Bearish")]
    return next((name for cutoff, name in bands if score >= cutoff), "Very Bearish")


def keyword_score(texts: list[str]) -> float:
    """Fallback when the LLM is unavailable: +1 per positive text, -1 per negative, mapped to 0..10."""
    if not texts:
        return 5.0
    raw = sum(any(w in t.lower() for w in POSITIVE) - any(w in t.lower() for w in NEGATIVE) for t in texts)
    return max(0.0, min(10.0, 5 + 2 * raw))


def mention_spike(social: SocialStats) -> float:
    return social.reddit_mentions / max(social.reddit_mentions_baseline, MIN_BASELINE_MENTIONS)


def blend_stocktwits(tone: float, social: SocialStats, weight: float) -> float:
    bulls, bears = social.stocktwits_bullish, social.stocktwits_bearish
    if bulls is None or bears is None or bulls + bears == 0:
        return tone                                         # source not available: tone only
    return (1 - weight) * tone + weight * 10 * bulls / (bulls + bears)


def score_one(symbol: str, data: DataHub, llm: LLMClient, as_of: datetime, stocktwits_weight: float) -> SentimentScore:
    news = data.news.headlines(symbol, as_of)
    social = data.social.stats(symbol, as_of)
    news_lines = [f"{h.title}. {h.summary}".strip() for h in news]
    texts = news_lines + social.reddit_sample_posts

    tone, confidence, catalyst = keyword_score(texts), "low", (news[0].title if news else None)
    if texts:                                               # nothing to read = neutral, no LLM call
        try:
            prompt = (f"Score the sentiment for the stock {symbol} from 0 (very bearish) to 10 (very bullish). "
                      f"News: {news_lines}. Reddit posts: {social.reddit_sample_posts or 'none'}. "
                      "Name the main catalyst or null. Ignore items not about this company.")
            answer = llm.generate(prompt, SentimentLLMOutput, tier="fast")
            tone, confidence, catalyst = answer.score, answer.confidence, answer.catalyst or catalyst
        except LLMError:
            pass

    final = blend_stocktwits(tone, social, stocktwits_weight)
    spike = mention_spike(social)
    return SentimentScore(
        symbol=symbol, band=band_for(final), score=round(final, 2), confidence=confidence,
        mention_spike=round(spike, 2), hype_warning=spike >= HYPE_SPIKE and final >= HYPE_SCORE,
        catalyst=catalyst,
    )


def run(symbols: list[str], data: DataHub, llm: LLMClient, as_of: datetime,
        stocktwits_weight: float) -> list[SentimentScore]:
    return [score_one(s, data, llm, as_of, stocktwits_weight) for s in symbols]
