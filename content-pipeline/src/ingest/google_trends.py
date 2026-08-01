import asyncio
import logging

from src.ingest.base import RawSignal, SourceUnavailable, TrendSource
from src.scoring.normalize import normalize

logger = logging.getLogger(__name__)


def _fetch_trending_sync() -> list[str]:
    # pytrends is unofficial and rate-limits aggressively; it is imported lazily so a
    # broken install can't take down the other sources, and any failure surfaces as
    # SourceUnavailable via the async wrapper.
    from pytrends.request import TrendReq

    pytrends = TrendReq(hl="en-IN", tz=330, retries=2, backoff_factor=4)
    df = pytrends.trending_searches(pn="india")
    return [str(t) for t in df[0].tolist()]


class GoogleTrendsSource(TrendSource):
    name = "google_trends"

    async def fetch(self) -> list[RawSignal]:
        try:
            topics = await asyncio.to_thread(_fetch_trending_sync)
        except Exception as exc:
            raise SourceUnavailable(f"google_trends: {exc}") from exc

        signals: list[RawSignal] = []
        for rank, topic in enumerate(topics, start=1):
            norm = normalize(topic)
            if not norm:
                continue
            signals.append(
                RawSignal(
                    # Trending searches carry no stable ID; the normalized topic is
                    # the identity, and (source, external_id, observed_at) dedupes.
                    external_id=norm,
                    topic_raw=topic,
                    metric_value=None,
                    raw={"topic": topic, "rank": rank, "geo": "india"},
                )
            )
        return signals
