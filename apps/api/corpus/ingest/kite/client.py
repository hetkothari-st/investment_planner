"""Rate-limited async wrapper over the (sync) kiteconnect SDK.

Chunking: Kite serves ~2000 daily candles per historical_data request, so a
10-year backfill is 2 requests per symbol. Chunk boundaries are computed here
and golden-tested without any network.
"""

import asyncio
from datetime import date, timedelta
from typing import Any

from kiteconnect import KiteConnect
from kiteconnect.exceptions import TokenException
from redis.asyncio import Redis

from corpus.config import get_settings
from corpus.ingest.kite.auth import get_access_token, mark_degraded
from corpus.ingest.ratelimit import TokenBucket

MAX_CANDLES_PER_REQUEST = 2000
HISTORICAL_RATE_PER_SEC = 3.0
QUOTE_RATE_PER_SEC = 1.0


def historical_chunks(since: date, until: date) -> list[tuple[date, date]]:
    """Split [since, until] into inclusive windows of <= MAX_CANDLES_PER_REQUEST days.

    Calendar days over-count trading days, so each chunk stays safely inside
    Kite's candle cap. Returns [] when since > until.
    """
    chunks: list[tuple[date, date]] = []
    start = since
    while start <= until:
        end = min(start + timedelta(days=MAX_CANDLES_PER_REQUEST - 1), until)
        chunks.append((start, end))
        start = end + timedelta(days=1)
    return chunks


class KiteClient:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        self._historical_bucket = TokenBucket(
            redis, "kite:historical", HISTORICAL_RATE_PER_SEC
        )
        self._quote_bucket = TokenBucket(redis, "kite:quote", QUOTE_RATE_PER_SEC)
        self._kite: KiteConnect | None = None

    async def _connected(self) -> KiteConnect:
        if self._kite is None:
            token = await get_access_token(self.redis)
            if token is None:
                raise TokenException("No Kite access token in Redis; re-authenticate")
            kite = KiteConnect(api_key=get_settings().kite_api_key)
            kite.set_access_token(token)
            self._kite = kite
        return self._kite

    async def _call(self, bucket: TokenBucket, fn, *args: Any, **kwargs: Any) -> Any:
        kite = await self._connected()
        await bucket.acquire()
        try:
            return await asyncio.to_thread(getattr(kite, fn), *args, **kwargs)
        except TokenException:
            await mark_degraded(self.redis, f"Kite token rejected during {fn}")
            raise

    async def instruments(self, exchange: str | None = None) -> list[dict[str, Any]]:
        if exchange:
            return await self._call(self._historical_bucket, "instruments", exchange)
        return await self._call(self._historical_bucket, "instruments")

    async def historical_daily(
        self, instrument_token: int, since: date, until: date
    ) -> list[dict[str, Any]]:
        """Unadjusted daily candles for [since, until], chunked to Kite's cap."""
        candles: list[dict[str, Any]] = []
        for start, end in historical_chunks(since, until):
            batch = await self._call(
                self._historical_bucket,
                "historical_data",
                instrument_token,
                start,
                end,
                "day",
                False,  # continuous
                False,  # oi
            )
            candles.extend(batch)
        return candles
