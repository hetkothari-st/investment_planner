"""Simulated positions: open, mark daily, close. Docs/08.

thesis_snapshot_md is copied by value at open and never regenerated — the
frozen copy is the entire scientific value of the feature.
"""

import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from corpus.db.models import OhlcvDaily, Recommendation, SimMark, SimPosition
from corpus.sim.costs import buy_costs, sell_costs, slipped_price

PAISE = Decimal("0.01")
PCT = Decimal("0.0001")


class SimError(Exception):
    pass


async def last_close(
    session: AsyncSession,
    instrument_token: int,
    on_or_before: date,
    strict: bool = False,
) -> tuple[date, Decimal] | None:
    """Latest close on or before the date; strict=True means strictly
    before (the prior session, used by CROSSES_* falsifiers)."""
    cutoff = (
        OhlcvDaily.trade_date < on_or_before
        if strict
        else OhlcvDaily.trade_date <= on_or_before
    )
    row = (
        await session.execute(
            select(OhlcvDaily.trade_date, OhlcvDaily.close)
            .where(
                OhlcvDaily.instrument_token == instrument_token,
                cutoff,
                OhlcvDaily.close.is_not(None),
            )
            .order_by(OhlcvDaily.trade_date.desc())
            .limit(1)
        )
    ).first()
    return (row.trade_date, row.close) if row else None


async def open_simulated(
    session: AsyncSession,
    recommendation_id: uuid.UUID,
    amount_inr: Decimal,
    opened_on: date,
    price: Decimal | None = None,
) -> SimPosition:
    """Open a paper position against a recommendation. Price defaults to the
    latest close for the instrument; a manual price is allowed because manual
    theses may predate any OHLCV backfill."""
    rec = await session.get(Recommendation, recommendation_id)
    if rec is None:
        raise SimError("Recommendation not found")
    if rec.status != "LIVE":
        raise SimError(f"Recommendation is {rec.status}, not LIVE")

    if price is None:
        if rec.instrument_token is None:
            raise SimError("No instrument token and no manual price given")
        latest = await last_close(session, rec.instrument_token, opened_on)
        if latest is None:
            raise SimError("No OHLCV data for this instrument; give a manual price")
        price = latest[1]

    entry_price = slipped_price(price, "BUY")
    qty = int(amount_inr // entry_price)
    if qty < 1:
        raise SimError("Amount too small for one share at entry price")

    position = SimPosition(
        id=uuid.uuid4(),
        recommendation_id=rec.id,
        isin=rec.isin,
        instrument_token=rec.instrument_token,
        opened_on=opened_on,
        qty=qty,
        entry_price=entry_price,
        entry_costs_inr=buy_costs(entry_price, qty).total,
        thesis_snapshot_md=rec.report_md,  # FROZEN. Never regenerated.
    )
    session.add(position)
    await session.commit()
    return position


def mark_values(
    qty: int,
    entry_price: Decimal,
    entry_costs: Decimal,
    close: Decimal,
    running_peak: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """(mtm_inr, unrealised_pct, drawdown_from_peak_pct) — docs/08 formulas."""
    invested = qty * entry_price
    mtm = (qty * close - invested - entry_costs).quantize(PAISE, ROUND_HALF_UP)
    unrealised = (mtm / invested * 100).quantize(PCT, ROUND_HALF_UP)
    drawdown = ((close - running_peak) / running_peak * 100).quantize(PCT, ROUND_HALF_UP)
    return mtm, unrealised, drawdown


async def mark_position(
    session: AsyncSession, position: SimPosition, trade_date: date, close: Decimal
) -> SimMark:
    prior_peak = (
        await session.execute(
            select(SimMark.close_price)
            .where(SimMark.position_id == position.id, SimMark.trade_date < trade_date)
            .order_by(SimMark.close_price.desc())
            .limit(1)
        )
    ).scalar()
    peak = max(position.entry_price, prior_peak or Decimal(0), close)
    mtm, unrealised, drawdown = mark_values(
        position.qty, position.entry_price, position.entry_costs_inr, close, peak
    )
    mark = SimMark(
        position_id=position.id,
        trade_date=trade_date,
        close_price=close,
        mtm_inr=mtm,
        unrealised_pct=unrealised,
        drawdown_from_peak_pct=drawdown,
    )
    await session.merge(mark)  # idempotent on (position, date)
    return mark


async def mark_open_positions(session: AsyncSession, trade_date: date) -> int:
    """Pipeline step 9: mark every open position from ohlcv_daily."""
    positions = (
        (
            await session.execute(
                select(SimPosition).where(SimPosition.closed_on.is_(None))
            )
        )
        .scalars()
        .all()
    )
    marked = 0
    for pos in positions:
        if pos.instrument_token is None:
            continue
        latest = await last_close(session, pos.instrument_token, trade_date)
        if latest is None:
            continue
        await mark_position(session, pos, trade_date, latest[1])
        marked += 1
    await session.commit()
    return marked


async def close_position(
    session: AsyncSession,
    position_id: uuid.UUID,
    closed_on: date,
    reason: str,
    journal_note: str | None,
    price: Decimal | None = None,
) -> SimPosition:
    pos = await session.get(SimPosition, position_id)
    if pos is None:
        raise SimError("Position not found")
    if pos.closed_on is not None:
        raise SimError("Position already closed")

    if price is None:
        if pos.instrument_token is None:
            raise SimError("No instrument token and no manual price given")
        latest = await last_close(session, pos.instrument_token, closed_on)
        if latest is None:
            raise SimError("No OHLCV data; give a manual price")
        price = latest[1]

    exit_price = slipped_price(price, "SELL")
    pos.closed_on = closed_on
    pos.exit_price = exit_price
    pos.exit_costs_inr = sell_costs(exit_price, pos.qty).total
    pos.close_reason = reason
    pos.journal_note = journal_note
    await session.commit()
    return pos


def realised_pnl_inr(pos: SimPosition) -> Decimal:
    """Net realised P&L: exit value − entry value − both cost legs."""
    if pos.exit_price is None or pos.exit_costs_inr is None:
        raise SimError("Position not closed")
    gross = pos.qty * pos.exit_price - pos.qty * pos.entry_price
    return (gross - pos.entry_costs_inr - pos.exit_costs_inr).quantize(
        PAISE, ROUND_HALF_UP
    )
