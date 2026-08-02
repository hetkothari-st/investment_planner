"""Kite Connect auth — docs/02-DATA-LAYER.md.

Access tokens expire daily (Kite invalidates around 06:00 IST). The token is
held in Redis with a TTL to the next 06:00 IST. On TokenException the pipeline
is marked degraded and the UI surfaces a re-auth prompt; nothing retries
silently.
"""

import asyncio
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from kiteconnect import KiteConnect
from redis.asyncio import Redis

from corpus.config import get_settings

IST = ZoneInfo("Asia/Kolkata")
ACCESS_TOKEN_KEY = "kite:access_token"
DEGRADED_KEY = "pipeline:degraded"


def _kite() -> KiteConnect:
    return KiteConnect(api_key=get_settings().kite_api_key)


def login_url() -> str:
    return _kite().login_url()


def seconds_to_next_expiry(now: datetime | None = None) -> int:
    """Seconds until the next 06:00 IST, when Kite invalidates tokens."""
    now = now or datetime.now(UTC)
    now_ist = now.astimezone(IST)
    expiry = datetime.combine(now_ist.date(), time(6, 0), tzinfo=IST)
    if now_ist >= expiry:
        expiry += timedelta(days=1)
    return int((expiry - now_ist).total_seconds())


async def exchange_and_store(request_token: str, redis: Redis) -> str:
    kite = _kite()
    session = await asyncio.to_thread(
        kite.generate_session, request_token, api_secret=get_settings().kite_api_secret
    )
    token: str = session["access_token"]
    await redis.set(ACCESS_TOKEN_KEY, token, ex=seconds_to_next_expiry())
    await redis.delete(DEGRADED_KEY)
    return token


async def get_access_token(redis: Redis) -> str | None:
    raw = await redis.get(ACCESS_TOKEN_KEY)
    return raw.decode() if isinstance(raw, bytes) else raw


async def mark_degraded(redis: Redis, reason: str) -> None:
    await redis.set(DEGRADED_KEY, reason)


async def degraded_reason(redis: Redis) -> str | None:
    raw = await redis.get(DEGRADED_KEY)
    return raw.decode() if isinstance(raw, bytes) else raw
