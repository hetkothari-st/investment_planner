"""Token-bucket rate limiter backed by Redis — docs/01-ARCHITECTURE.md.

Kite limits: 3 req/s historical, 1 req/s quote. The bucket state lives in Redis
so that the API process and backfill script share one budget.
"""

import asyncio
import time

from redis.asyncio import Redis


class TokenBucket:
    def __init__(
        self,
        redis: Redis,
        key: str,
        rate_per_sec: float,
        burst: int | None = None,
    ) -> None:
        self.redis = redis
        self.key = f"ratelimit:{key}"
        self.rate = rate_per_sec
        self.burst = burst if burst is not None else max(1, int(rate_per_sec))

    async def _try_acquire(self) -> float:
        """Attempt to take one token. Returns 0 on success, else seconds to wait."""
        now = time.monotonic()
        state = await self.redis.hgetall(self.key)
        if state:
            tokens = float(state[b"tokens"])
            stamp = float(state[b"stamp"])
            tokens = min(self.burst, tokens + (now - stamp) * self.rate)
        else:
            tokens = float(self.burst)
        if tokens >= 1.0:
            await self.redis.hset(self.key, mapping={"tokens": tokens - 1.0, "stamp": now})
            return 0.0
        await self.redis.hset(self.key, mapping={"tokens": tokens, "stamp": now})
        return (1.0 - tokens) / self.rate

    async def acquire(self) -> None:
        while True:
            wait = await self._try_acquire()
            if wait <= 0:
                return
            await asyncio.sleep(wait)
