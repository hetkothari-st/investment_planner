from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fakeredis.aioredis import FakeRedis

from corpus.ingest.kite.auth import seconds_to_next_expiry
from corpus.ingest.kite.client import MAX_CANDLES_PER_REQUEST, historical_chunks
from corpus.ingest.ratelimit import TokenBucket

IST = ZoneInfo("Asia/Kolkata")


def test_chunks_cover_range_without_overlap():
    since, until = date(2016, 7, 30), date(2026, 7, 30)
    chunks = historical_chunks(since, until)
    assert chunks[0][0] == since
    assert chunks[-1][1] == until
    for (_, prev_end), (next_start, _) in zip(chunks, chunks[1:], strict=False):
        assert next_start == prev_end + timedelta(days=1)
    for start, end in chunks:
        assert (end - start).days + 1 <= MAX_CANDLES_PER_REQUEST
    # 10 years of dailies ≈ 2 requests per symbol (docs/02 backfill plan)
    assert len(chunks) == 2


def test_chunks_single_day_and_empty():
    d = date(2026, 7, 30)
    assert historical_chunks(d, d) == [(d, d)]
    assert historical_chunks(d, d - timedelta(days=1)) == []


def test_token_expiry_before_6am_ist():
    now = datetime(2026, 7, 30, 5, 0, tzinfo=IST)
    assert seconds_to_next_expiry(now) == 3600


def test_token_expiry_after_6am_ist_rolls_to_tomorrow():
    now = datetime(2026, 7, 30, 7, 0, tzinfo=IST)
    assert seconds_to_next_expiry(now) == 23 * 3600


async def test_token_bucket_depletes_then_refuses():
    bucket = TokenBucket(FakeRedis(), "test", rate_per_sec=3.0, burst=3)
    for _ in range(3):
        assert await bucket._try_acquire() == 0.0
    wait = await bucket._try_acquire()
    assert 0 < wait <= 1 / 3 + 0.01
