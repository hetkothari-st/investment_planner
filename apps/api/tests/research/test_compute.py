"""Compute orchestrator: persists values and gaps, idempotent re-runs."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from corpus.db.models import Instrument, MetricGap, MetricValueRow, OhlcvDaily, Shareholding
from corpus.research.compute import compute_universe_metrics

D = Decimal
AS_OF = date(2026, 7, 30)
BENCH = 256265


async def seed(session, token: int, isin: str, days: int, base: float = 100.0):
    session.add(
        Instrument(instrument_token=token, tradingsymbol=isin[-4:], exchange="NSE",
                   isin=isin)
    )
    d = AS_OF
    added = 0
    price = base
    while added < days:
        if d.weekday() < 5:
            session.add(
                OhlcvDaily(
                    instrument_token=token, trade_date=d,
                    close=D(str(round(price, 2))),
                    adj_close=D(str(round(price, 2))),
                    high=D(str(round(price * 1.01, 2))),
                    low=D(str(round(price * 0.99, 2))),
                    volume=100_000,
                )
            )
            price *= 0.9996  # gentle drift so returns are nonzero
            added += 1
        d -= timedelta(days=1)
    await session.commit()


async def test_compute_persists_values_and_gaps(session):
    await seed(session, BENCH, "INEBENCHMARK", 300)
    await seed(session, 111, "INE111LONGX", 300)   # enough for 1y, not 3y
    await seed(session, 222, "INE222SHORT", 40)    # short history: mostly gaps
    session.add(
        Shareholding(isin="INE111LONGX", period_end=date(2026, 6, 30),
                     promoter_pct=D("54.2"), promoter_pledged_pct=D("2.1"),
                     fii_pct=D("18.0"), dii_pct=D("11.0"), source="test")
    )
    await session.commit()

    totals = await compute_universe_metrics(session, AS_OF, benchmark_token=BENCH)
    assert totals["symbols"] == 3
    assert totals["values"] > 0
    assert totals["gaps"] > 0

    values = {
        (r.isin, r.field_id): r
        for r in (await session.execute(select(MetricValueRow))).scalars()
    }
    gaps = {
        (r.isin, r.field_id): r.reason
        for r in (await session.execute(select(MetricGap))).scalars()
    }

    # 1y metrics exist for the long-history name, gap for the short one
    assert ("INE111LONGX", "risk.vol_ann_1y") in values
    assert gaps[("INE222SHORT", "risk.vol_ann_1y")] == "INSUFFICIENT_HISTORY"
    # 3y drawdown is a gap even for 300 days of history
    assert gaps[("INE111LONGX", "risk.max_dd_3y")] == "INSUFFICIENT_HISTORY"
    # shareholding flowed through
    assert values[("INE111LONGX", "gov.pledge_pct")].value == D("2.100")
    # units come from the registry
    assert values[("INE111LONGX", "liq.adv_20d_inr")].unit == "inr_cr"

    # Idempotent: identical re-run writes zero value rows
    totals2 = await compute_universe_metrics(session, AS_OF, benchmark_token=BENCH)
    assert totals2["values"] == 0
