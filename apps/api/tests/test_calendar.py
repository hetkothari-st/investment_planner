"""Calendar is observed from index bars, never inferred from weekday rules."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from corpus.db.models import OhlcvDaily, TradingDay
from corpus.ingest.jobs.calendar import (
    NIFTY50_INSTRUMENT_TOKEN,
    build_calendar_from_index,
    trading_days_between,
)


async def _seed_index_bars(session, dates: list[date]):
    for d in dates:
        session.add(
            OhlcvDaily(
                instrument_token=NIFTY50_INSTRUMENT_TOKEN,
                trade_date=d,
                close=Decimal("22000"),
                source="kite",
            )
        )
    await session.commit()


async def test_calendar_from_observed_bars(session):
    # Mon 2024-01-22 was an unscheduled NSE holiday-like case; model it as:
    # bars on Mon 15th, Tue 16th, Thu 18th (Wed 17th closed), Sat 20th (special session).
    traded = [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 18), date(2024, 1, 20)]
    await _seed_index_bars(session, traded)

    n = await build_calendar_from_index(session, date(2024, 1, 15), date(2024, 1, 21))
    await session.commit()
    assert n == 7  # every calendar day gets a row

    days = await trading_days_between(session, date(2024, 1, 15), date(2024, 1, 21))
    assert days == traded

    wed = await session.get(TradingDay, date(2024, 1, 17))
    assert wed is not None and wed.is_trading_day is False
    assert "observed" in (wed.note or "")

    sat = await session.get(TradingDay, date(2024, 1, 20))
    assert sat is not None and sat.is_trading_day is True
    assert sat.note == "weekend session"

    sun = await session.get(TradingDay, date(2024, 1, 21))
    assert sun is not None and sun.is_trading_day is False


async def test_calendar_rerun_is_idempotent(session):
    await _seed_index_bars(session, [date(2024, 2, 1)])
    first = await build_calendar_from_index(session, date(2024, 2, 1), date(2024, 2, 3))
    await session.commit()
    assert first == 3
    second = await build_calendar_from_index(session, date(2024, 2, 1), date(2024, 2, 3))
    await session.commit()
    assert second == 0

    rows = (await session.execute(select(TradingDay))).scalars().all()
    assert len(rows) == 3
