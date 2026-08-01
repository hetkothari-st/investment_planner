import asyncio
import logging
import sys
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.db import SessionLocal
from src.ingest.base import RawSignal, TrendSource
from src.ingest.google_trends import GoogleTrendsSource
from src.ingest.reddit import RedditSource
from src.ingest.tiktok_cc import TikTokCreativeCenterSource
from src.ingest.youtube_trending import YouTubeTrendingSource
from src.models.trend import TrendSignal
from src.scoring.normalize import normalize

logger = logging.getLogger("ingest")

SOURCES: list[TrendSource] = [
    TikTokCreativeCenterSource(),
    YouTubeTrendingSource(),
    RedditSource(),
    GoogleTrendsSource(),
]


async def _fetch_source(source: TrendSource) -> tuple[str, list[RawSignal]]:
    try:
        signals = await source.fetch()
        logger.info("stage=fetch source=%s status=ok signals=%d", source.name, len(signals))
        return source.name, signals
    except Exception as exc:
        # Any single source being down is non-fatal — log and continue.
        logger.warning("stage=fetch source=%s status=failed error=%s", source.name, exc)
        return source.name, []


async def persist_signals(
    by_source: dict[str, list[RawSignal]],
    observed_at: datetime,
) -> int:
    """Insert signals with observed_at truncated to the minute, so a re-run within
    the same minute dedupes cleanly on uq_signal via ON CONFLICT DO NOTHING."""
    from src.ingest.niche import classify_niches

    rows = []
    to_classify: dict[str, tuple[str, str]] = {}
    for source_name, signals in by_source.items():
        for sig in signals:
            norm = normalize(sig.topic_raw)
            if not norm:
                continue
            key = f"{source_name}:{sig.external_id}"
            if sig.niche is None:
                to_classify[key] = (sig.topic_raw, norm)
            rows.append(
                {
                    "source": source_name,
                    "external_id": sig.external_id,
                    "topic_raw": sig.topic_raw,
                    "topic_norm": norm,
                    "niche": sig.niche,
                    "metric_value": sig.metric_value,
                    "observed_at": observed_at,
                    "raw": sig.raw,
                    "_key": key,
                }
            )

    if not rows:
        return 0

    try:
        niches = await classify_niches(to_classify)
    except Exception as exc:
        logger.warning("stage=classify status=failed error=%s", exc)
        niches = {}
    for row in rows:
        key = row.pop("_key")
        if row["niche"] is None:
            row["niche"] = niches.get(key)

    async with SessionLocal() as session:
        stmt = (
            pg_insert(TrendSignal)
            .values(rows)
            .on_conflict_do_nothing(constraint="uq_signal")
            .returning(TrendSignal.id)
        )
        result = await session.execute(stmt)
        inserted = len(result.fetchall())
        await session.commit()
    return inserted


async def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    observed_at = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    results = await asyncio.gather(*(_fetch_source(s) for s in SOURCES))
    by_source = {name: signals for name, signals in results}

    inserted = await persist_signals(by_source, observed_at)
    total = sum(len(s) for s in by_source.values())
    logger.info(
        "stage=persist status=ok fetched=%d inserted=%d deduped=%d observed_at=%s",
        total, inserted, total - inserted, observed_at.isoformat(),
    )


if __name__ == "__main__":
    asyncio.run(run())
