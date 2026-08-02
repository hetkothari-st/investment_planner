"""M1 acceptance: re-running a day changes zero rows, proved by row-hash comparison."""

import hashlib
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from corpus.db.models import OhlcvDaily
from corpus.db.upsert import upsert_rows

D = Decimal


def _rows(instrument_token: int = 101) -> list[dict]:
    return [
        {
            "instrument_token": instrument_token,
            "trade_date": date(2024, 1, d),
            "open": D("100.0"),
            "high": D("105.0"),
            "low": D("99.0"),
            "close": D(f"10{d}.5"),
            "volume": 1000 * d,
            "adj_close": None,
            "source": "kite",
        }
        for d in (1, 2, 3)
    ]


async def _table_hash(session) -> str:
    result = await session.execute(
        select(
            OhlcvDaily.instrument_token,
            OhlcvDaily.trade_date,
            OhlcvDaily.open,
            OhlcvDaily.high,
            OhlcvDaily.low,
            OhlcvDaily.close,
            OhlcvDaily.volume,
            OhlcvDaily.adj_close,
            OhlcvDaily.source,
        ).order_by(OhlcvDaily.instrument_token, OhlcvDaily.trade_date)
    )
    payload = repr(result.all()).encode()
    return hashlib.sha256(payload).hexdigest()


async def test_rerun_changes_zero_rows(session):
    keys = ["instrument_token", "trade_date"]
    skip = ("ingested_at", "adj_close")

    first = await upsert_rows(session, OhlcvDaily.__table__, _rows(), keys, skip)
    await session.commit()
    assert first == 3
    hash_before = await _table_hash(session)

    second = await upsert_rows(session, OhlcvDaily.__table__, _rows(), keys, skip)
    await session.commit()
    assert second == 0, "identical re-run must write zero rows"
    assert await _table_hash(session) == hash_before


async def test_changed_value_writes_exactly_that_row(session):
    keys = ["instrument_token", "trade_date"]
    skip = ("ingested_at", "adj_close")
    await upsert_rows(session, OhlcvDaily.__table__, _rows(), keys, skip)
    await session.commit()

    amended = _rows()
    amended[1]["close"] = D("999.9")  # exchange restated one close
    written = await upsert_rows(session, OhlcvDaily.__table__, amended, keys, skip)
    await session.commit()
    assert written == 1

    restated = await session.scalar(
        select(OhlcvDaily.close).where(
            OhlcvDaily.instrument_token == 101,
            OhlcvDaily.trade_date == date(2024, 1, 2),
        )
    )
    assert restated == D("999.9")
