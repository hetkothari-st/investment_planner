"""M4 acceptance: open -> 30 marks -> close reconciles to the paise against a
hand-computed contract-note fixture.

Fixture arithmetic (rates from config/costs.v1.yaml):
  Close 500.00, slippage floor 0.05% -> entry 500.25; ₹50,100 buys qty 100.
  Buy turnover 50,025:
    STT 0.1%            = 50.025
    exchange 0.00297%   =  1.4857425
    SEBI 0.0001%        =  0.050025
    stamp 0.015%        =  7.50375
    GST 18% x (exch+SEBI)= 0.27643815
    total               = 59.34095565 -> ₹59.34
  Exit at close 530 -> 529.735 after slippage. Sell turnover 52,973.50:
    STT 52.9735 + exch 1.57331295 + SEBI 0.0529735
    + GST 0.292731561 + DP 15.93   = 70.82251801 -> ₹70.82
  Realised P&L = 52,973.50 - 50,025 - 59.34 - 70.82 = ₹2,818.34
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from corpus.db.models import OhlcvDaily, SimMark
from corpus.sim.positions import (
    close_position,
    mark_open_positions,
    open_simulated,
    realised_pnl_inr,
)
from corpus.sim.theses import FalsifierIn, ManualThesisIn, create_manual_thesis

D = Decimal
TOKEN = 424961
OPEN_DAY = date(2026, 6, 1)


def thesis_body() -> ManualThesisIn:
    return ManualThesisIn(
        isin="INE000TEST01",
        tradingsymbol="TESTCO",
        instrument_token=TOKEN,
        horizon="MID",
        expires_on=date(2027, 6, 1),
        ref_price=D("500"),
        band_bear_pct=D("-15"),
        band_base_pct=D("8"),
        band_bull_pct=D("25"),
        conviction="MODERATE",
        suggested_size_inr=D("50100"),
        thesis_md="Margin expansion holds while the market prices a slowdown.",
        falsifiers=[
            FalsifierIn(
                field_id="fin.ebitda_margin_ttm",
                operator="LT",
                threshold=D("14"),
                human_text="TTM EBITDA margin falls below 14%",
            )
        ],
    )


async def seed_closes(session, closes: dict[date, Decimal]):
    for d, c in closes.items():
        session.add(
            OhlcvDaily(instrument_token=TOKEN, trade_date=d, close=c, source="kite")
        )
    await session.commit()


def trading_days(n: int) -> list[date]:
    """n weekdays starting the day after OPEN_DAY."""
    days, d = [], OPEN_DAY
    while len(days) < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days.append(d)
    return days


async def test_open_thirty_marks_close_reconciles_to_the_paise(session):
    rec = await create_manual_thesis(session, thesis_body(), OPEN_DAY)
    await seed_closes(session, {OPEN_DAY: D("500")})

    pos = await open_simulated(session, rec.id, D("50100"), OPEN_DAY)
    assert pos.qty == 100
    assert pos.entry_price == D("500.2500")
    assert pos.entry_costs_inr == D("59.34")

    # 30 marks: rise to 520, dip to 515, finish at 530
    days = trading_days(30)
    closes: dict[date, Decimal] = {}
    for i, d in enumerate(days, start=1):
        closes[d] = (
            D(500 + i) if i <= 20 else D("515") if i <= 29 else D("530")
        )
    await seed_closes(session, closes)
    for d in days:
        assert await mark_open_positions(session, d) == 1

    marks = {
        m.trade_date: m
        for m in (await session.execute(select(SimMark))).scalars()
    }
    assert len(marks) == 30

    # Day 20 (peak so far 520): mtm = 52,000 - 50,025 - 59.34 = 1,915.66
    m20 = marks[days[19]]
    assert m20.mtm_inr == D("1915.66")
    assert m20.unrealised_pct == D("3.8294")  # 1915.66/50025
    assert m20.drawdown_from_peak_pct == D("0.0000")

    # Day 25 (close 515 vs peak 520): drawdown (515-520)/520
    m25 = marks[days[24]]
    assert m25.drawdown_from_peak_pct == D("-0.9615")

    # Day 30: mtm = 53,000 - 50,025 - 59.34 = 2,915.66
    m30 = marks[days[29]]
    assert m30.mtm_inr == D("2915.66")
    assert m30.unrealised_pct == D("5.8284")  # 2915.66/50025

    closed = await close_position(
        session, pos.id, days[-1], "MANUAL", "Thesis played out faster than expected."
    )
    assert closed.exit_price == D("529.7350")
    assert closed.exit_costs_inr == D("70.82")
    assert realised_pnl_inr(closed) == D("2818.34")


async def test_thesis_snapshot_is_frozen_by_value(session):
    """M4 acceptance: nothing that happens later alters thesis_snapshot_md."""
    rec = await create_manual_thesis(session, thesis_body(), OPEN_DAY)
    original = rec.report_md
    await seed_closes(session, {OPEN_DAY: D("500")})
    pos = await open_simulated(session, rec.id, D("50100"), OPEN_DAY)
    assert pos.thesis_snapshot_md == original

    # Status flips (the one permitted recommendation change) leave it alone.
    rec.status = "INVALIDATED"
    await session.commit()
    refetched = await session.get(type(pos), pos.id, populate_existing=True)
    assert refetched.thesis_snapshot_md == original  # byte-identical


async def test_marking_is_idempotent(session):
    rec = await create_manual_thesis(session, thesis_body(), OPEN_DAY)
    day1 = trading_days(1)[0]
    await seed_closes(session, {OPEN_DAY: D("500"), day1: D("510")})
    await open_simulated(session, rec.id, D("50100"), OPEN_DAY)
    await mark_open_positions(session, day1)
    await mark_open_positions(session, day1)  # re-run the day
    marks = (await session.execute(select(SimMark))).scalars().all()
    assert len(marks) == 1
