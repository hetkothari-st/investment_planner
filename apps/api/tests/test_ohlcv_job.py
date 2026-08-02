"""OHLCV ingestion with a fake Kite client: partial tolerance + adjusted closes."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from corpus.db.models import CorporateAction, Instrument, OhlcvDaily
from corpus.ingest.jobs.ohlcv import ingest_ohlcv_daily, recompute_adjusted_closes

D = Decimal


class FakeKite:
    """Serves canned candles; token 999 always fails."""

    def __init__(self):
        self.candles = {
            101: [
                {"date": date(2024, 5, 30), "open": 990, "high": 1010, "low": 985,
                 "close": 1000.0, "volume": 5000},
                {"date": date(2024, 6, 3), "open": 200, "high": 208, "low": 199,
                 "close": 205.0, "volume": 25000},
            ]
        }

    async def historical_daily(self, token, since, until):
        if token == 999:
            raise TimeoutError("kite timeout")
        return self.candles.get(token, [])


async def test_partial_tolerance_one_bad_symbol(session):
    rec = await ingest_ohlcv_daily(
        session, FakeKite(), [101, 999], date(2024, 5, 1), date(2024, 6, 30),
        as_of=date(2024, 6, 30),
    )
    assert rec.rows_written == 2
    assert "999" in rec.errors
    assert rec.run.status == "PARTIAL"

    bars = (await session.execute(select(OhlcvDaily))).scalars().all()
    assert len(bars) == 2  # the good symbol landed despite the bad one


async def test_recompute_adjusted_closes(session):
    session.add(Instrument(instrument_token=101, tradingsymbol="TEST",
                           exchange="NSE", isin="INE000TEST01"))
    session.add(CorporateAction(isin="INE000TEST01", ex_date=date(2024, 6, 3),
                                action_type="SPLIT", ratio_from=D("10"),
                                ratio_to=D("2"), source="manual_csv"))
    await session.commit()

    await ingest_ohlcv_daily(
        session, FakeKite(), [101], date(2024, 5, 1), date(2024, 6, 30),
        as_of=date(2024, 6, 30),
    )
    changed = await recompute_adjusted_closes(session, 101)
    await session.commit()
    assert changed == 2

    adj = {
        b.trade_date: b.adj_close
        for b in (await session.execute(select(OhlcvDaily))).scalars()
    }
    assert adj[date(2024, 5, 30)] == D("200.0000")  # 1000 x 0.2
    assert adj[date(2024, 6, 3)] == D("205.0000")   # on/after ex-date: raw close

    # Second recompute with unchanged inputs writes nothing.
    assert await recompute_adjusted_closes(session, 101) == 0
