"""Trading calendar.

Historical trading days are *observed*, not inferred: a date is a trading day
iff the NIFTY 50 index has a bar for it. That captures ad-hoc sessions (Budget
Saturdays) and unscheduled closures exactly, because it is the record of what
actually traded. Future holidays cannot be observed, so they load from the
exchange's published list via load_holiday_csv.
"""

import csv
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from corpus.db.models import OhlcvDaily, TradingDay
from corpus.db.upsert import upsert_rows

NIFTY50_INSTRUMENT_TOKEN = 256265  # Kite token for NSE:NIFTY 50


async def build_calendar_from_index(
    session: AsyncSession,
    since: date,
    until: date,
    index_token: int = NIFTY50_INSTRUMENT_TOKEN,
) -> int:
    """Write trading_calendar rows for every date in [since, until]."""
    traded = set(
        (
            await session.execute(
                select(OhlcvDaily.trade_date).where(
                    OhlcvDaily.instrument_token == index_token,
                    OhlcvDaily.trade_date >= since,
                    OhlcvDaily.trade_date <= until,
                )
            )
        )
        .scalars()
        .all()
    )
    rows = []
    d = since
    while d <= until:
        is_weekend = d.weekday() >= 5
        rows.append(
            {
                "trade_date": d,
                "exchange": "NSE",
                "is_trading_day": d in traded,
                "note": (
                    "weekend session"
                    if d in traded and is_weekend
                    else "weekend"
                    if is_weekend
                    else None
                    if d in traded
                    else "closed (observed: no index bar)"
                ),
            }
        )
        d += timedelta(days=1)
    return await upsert_rows(session, TradingDay.__table__, rows, key_cols=["trade_date"])


async def load_holiday_csv(session: AsyncSession, path: Path) -> int:
    """Load published future holidays. CSV columns: date,note (ISO date)."""
    rows = []
    with path.open() as f:
        for line in csv.DictReader(f):
            d = date.fromisoformat(line["date"].strip())
            rows.append(
                {
                    "trade_date": d,
                    "exchange": "NSE",
                    "is_trading_day": False,
                    "note": line.get("note", "").strip() or "published holiday",
                }
            )
    return await upsert_rows(session, TradingDay.__table__, rows, key_cols=["trade_date"])


async def trading_days_between(
    session: AsyncSession, since: date, until: date
) -> list[date]:
    return list(
        (
            await session.execute(
                select(TradingDay.trade_date)
                .where(
                    TradingDay.trade_date >= since,
                    TradingDay.trade_date <= until,
                    TradingDay.is_trading_day.is_(True),
                )
                .order_by(TradingDay.trade_date)
            )
        )
        .scalars()
        .all()
    )
