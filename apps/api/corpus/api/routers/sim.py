"""Simulator + calibration routes. Thin over corpus/sim services."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from corpus.db.models import Falsifier, Recommendation, SimMark, SimPosition
from corpus.db.session import get_session
from corpus.planner.schemas import Money
from corpus.sim.analytics import xirr
from corpus.sim.calibration import (
    HorizonSummary,
    calibration_summary,
    score_expired_recommendations,
)
from corpus.sim.positions import (
    SimError,
    close_position,
    mark_open_positions,
    open_simulated,
    realised_pnl_inr,
)
from corpus.sim.theses import ManualThesisIn, create_manual_thesis

router = APIRouter(prefix="/sim", tags=["sim"])


class ThesisOut(BaseModel):
    id: uuid.UUID
    isin: str
    tradingsymbol: str | None
    horizon: str
    issued_at: datetime
    expires_on: date
    ref_price: Decimal
    band_bear_pct: Decimal
    band_base_pct: Decimal
    band_bull_pct: Decimal
    conviction: str
    suggested_size_inr: Money
    report_md: str
    status: str
    falsifiers: list[dict]


def _thesis_out(rec: Recommendation, falsifiers: list[Falsifier]) -> ThesisOut:
    return ThesisOut(
        id=rec.id,
        isin=rec.isin,
        tradingsymbol=rec.tradingsymbol,
        horizon=rec.horizon,
        issued_at=rec.issued_at,
        expires_on=rec.expires_on,
        ref_price=rec.ref_price,
        band_bear_pct=rec.band_bear_pct,
        band_base_pct=rec.band_base_pct,
        band_bull_pct=rec.band_bull_pct,
        conviction=rec.conviction,
        suggested_size_inr=rec.suggested_size_inr,
        report_md=rec.report_md,
        status=rec.status,
        falsifiers=[
            {
                "field_id": f.field_id,
                "operator": f.operator,
                "threshold": str(f.threshold),
                "human_text": f.human_text,
                "breached_at": f.breached_at.isoformat() if f.breached_at else None,
            }
            for f in falsifiers
        ],
    )


@router.post("/theses")
async def post_thesis(
    body: ManualThesisIn, session: AsyncSession = Depends(get_session)
) -> ThesisOut:
    rec = await create_manual_thesis(session, body, datetime.now(UTC).date())
    falsifiers = (
        (
            await session.execute(
                select(Falsifier).where(Falsifier.recommendation_id == rec.id)
            )
        )
        .scalars()
        .all()
    )
    return _thesis_out(rec, list(falsifiers))


@router.get("/theses")
async def list_theses(session: AsyncSession = Depends(get_session)) -> list[ThesisOut]:
    recs = (
        (
            await session.execute(
                select(Recommendation).order_by(Recommendation.issued_at.desc())
            )
        )
        .scalars()
        .all()
    )
    falsifiers = (await session.execute(select(Falsifier))).scalars().all()
    by_rec: dict[uuid.UUID, list[Falsifier]] = {}
    for f in falsifiers:
        by_rec.setdefault(f.recommendation_id, []).append(f)
    return [_thesis_out(r, by_rec.get(r.id, [])) for r in recs]


class OpenPositionIn(BaseModel):
    recommendation_id: uuid.UUID
    amount_inr: Money
    price: Decimal | None = None  # manual price when no OHLCV exists yet


class PositionOut(BaseModel):
    id: uuid.UUID
    recommendation_id: uuid.UUID
    isin: str
    opened_on: date
    qty: int
    entry_price: Decimal
    entry_costs_inr: Money
    closed_on: date | None
    exit_price: Decimal | None
    close_reason: str | None
    journal_note: str | None
    latest_mark: dict | None
    realised_pnl_inr: int | None  # paise
    holding_xirr_pct: Decimal | None
    thesis_snapshot_md: str


async def _position_out(session: AsyncSession, pos: SimPosition) -> PositionOut:
    latest = (
        await session.execute(
            select(SimMark)
            .where(SimMark.position_id == pos.id)
            .order_by(SimMark.trade_date.desc())
            .limit(1)
        )
    ).scalar()
    realised = None
    rate = None
    if pos.closed_on is not None and pos.exit_price is not None:
        pnl = realised_pnl_inr(pos)
        realised = int(pnl * 100)
        flows = [
            (pos.opened_on, -(pos.qty * pos.entry_price + pos.entry_costs_inr)),
            (
                pos.closed_on,
                pos.qty * pos.exit_price - (pos.exit_costs_inr or Decimal(0)),
            ),
        ]
        r = xirr(flows)
        rate = Decimal(str(round(r * 100, 2))) if r is not None else None
    return PositionOut(
        id=pos.id,
        recommendation_id=pos.recommendation_id,
        isin=pos.isin,
        opened_on=pos.opened_on,
        qty=pos.qty,
        entry_price=pos.entry_price,
        entry_costs_inr=pos.entry_costs_inr,
        closed_on=pos.closed_on,
        exit_price=pos.exit_price,
        close_reason=pos.close_reason,
        journal_note=pos.journal_note,
        latest_mark=(
            {
                "trade_date": latest.trade_date.isoformat(),
                "close_price": str(latest.close_price),
                "mtm_inr": int(latest.mtm_inr * 100),
                "unrealised_pct": str(latest.unrealised_pct),
                "drawdown_from_peak_pct": str(latest.drawdown_from_peak_pct),
            }
            if latest
            else None
        ),
        realised_pnl_inr=realised,
        holding_xirr_pct=rate,
        thesis_snapshot_md=pos.thesis_snapshot_md,
    )


@router.post("/positions")
async def post_position(
    body: OpenPositionIn, session: AsyncSession = Depends(get_session)
) -> PositionOut:
    try:
        pos = await open_simulated(
            session,
            body.recommendation_id,
            body.amount_inr,
            datetime.now(UTC).date(),
            price=body.price,
        )
    except SimError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return await _position_out(session, pos)


@router.get("/positions")
async def list_positions(
    session: AsyncSession = Depends(get_session),
) -> list[PositionOut]:
    positions = (
        (
            await session.execute(
                select(SimPosition).order_by(SimPosition.opened_on.desc())
            )
        )
        .scalars()
        .all()
    )
    return [await _position_out(session, p) for p in positions]


class ClosePositionIn(BaseModel):
    reason: str  # MANUAL | FALSIFIER | EXPIRY | THESIS_CHANGED
    journal_note: str  # "Why now?" — required; it teaches more than the P&L
    price: Decimal | None = None


@router.post("/positions/{position_id}/close")
async def post_close(
    position_id: uuid.UUID,
    body: ClosePositionIn,
    session: AsyncSession = Depends(get_session),
) -> PositionOut:
    try:
        pos = await close_position(
            session,
            position_id,
            datetime.now(UTC).date(),
            body.reason,
            body.journal_note,
            price=body.price,
        )
    except SimError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return await _position_out(session, pos)


class MarkRunOut(BaseModel):
    marked: int
    scored: int
    skipped: list[str]


@router.post("/run-daily")
async def run_daily(session: AsyncSession = Depends(get_session)) -> MarkRunOut:
    """Manual trigger for pipeline steps 9-10 until the nightly scheduler
    lands with the full pipeline (M5+)."""
    today = datetime.now(UTC).date()
    marked = await mark_open_positions(session, today)
    scored, skipped = await score_expired_recommendations(session, today)
    return MarkRunOut(marked=marked, scored=scored, skipped=skipped)


@router.get("/calibration")
async def get_calibration(
    session: AsyncSession = Depends(get_session),
) -> list[HorizonSummary]:
    return await calibration_summary(session)
