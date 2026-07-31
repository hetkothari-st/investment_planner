"""Alert centre routes — docs/05 breach flow, docs/10 M8.

The check endpoint is pipeline step 8 exposed by hand; the live layer (M9)
schedules it nightly. Everything here is deterministic and idempotent.
"""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from corpus.db.models import Alert, Falsifier, Recommendation
from corpus.db.session import get_session
from corpus.sim.falsifiers import check_falsifiers, is_breached, observe

router = APIRouter(prefix="/alerts", tags=["alerts"])


class CheckOut(BaseModel):
    as_of: str
    checked: int
    breached: int
    skipped: list[str]


@router.post("/check")
async def run_check(session: AsyncSession = Depends(get_session)) -> CheckOut:
    """Evaluate every unbreached falsifier on every LIVE recommendation.
    Safe to re-run: a breached falsifier is never re-alerted."""
    report = await check_falsifiers(session, datetime.now(UTC).date())
    return CheckOut(
        as_of=report.as_of.isoformat(),
        checked=report.checked,
        breached=report.breached,
        skipped=report.skipped,
    )


class AlertOut(BaseModel):
    id: int
    kind: str
    recommendation_id: str
    isin: str
    tradingsymbol: str | None
    horizon: str
    field_id: str
    operator: str
    threshold: Decimal
    observed_value: Decimal
    observed_as_of: str
    thesis_line: str
    thesis_line_found: bool
    raised_at: datetime
    acknowledged_at: datetime | None


def _alert_out(a: Alert) -> AlertOut:
    return AlertOut(
        id=a.id,
        kind=a.kind,
        recommendation_id=str(a.recommendation_id),
        isin=a.isin,
        tradingsymbol=a.tradingsymbol,
        horizon=a.horizon,
        field_id=a.field_id,
        operator=a.operator,
        threshold=a.threshold,
        observed_value=a.observed_value,
        observed_as_of=a.observed_as_of.isoformat(),
        thesis_line=a.thesis_line,
        thesis_line_found=a.thesis_line_found,
        raised_at=a.raised_at,
        acknowledged_at=a.acknowledged_at,
    )


@router.get("")
async def list_alerts(
    include_acknowledged: bool = False,
    session: AsyncSession = Depends(get_session),
) -> list[AlertOut]:
    q = select(Alert).order_by(Alert.raised_at.desc(), Alert.id.desc())
    if not include_acknowledged:
        q = q.where(Alert.acknowledged_at.is_(None))
    return [_alert_out(a) for a in (await session.execute(q)).scalars()]


@router.post("/{alert_id}/ack")
async def acknowledge(
    alert_id: int, session: AsyncSession = Depends(get_session)
) -> AlertOut:
    alert = await session.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(404, "No such alert.")
    if alert.acknowledged_at is None:
        alert.acknowledged_at = datetime.now(UTC)
        await session.commit()
    return _alert_out(alert)


class LiveFalsifierOut(BaseModel):
    falsifier_id: str
    recommendation_id: str
    isin: str
    tradingsymbol: str | None
    horizon: str
    field_id: str
    operator: str
    threshold: Decimal
    human_text: str
    current_value: Decimal | None  # None: not resolvable — shown, not hidden
    observed_as_of: str | None
    breached: bool | None


@router.get("/live-falsifiers")
async def live_falsifiers(
    session: AsyncSession = Depends(get_session),
) -> list[LiveFalsifierOut]:
    """Every falsifier on a LIVE thesis with its current reading — the
    watch-list view. Distance to breach is the UI's arithmetic; the values
    here are the record."""
    as_of = datetime.now(UTC).date()
    recs = {
        r.id: r
        for r in (
            await session.execute(
                select(Recommendation).where(Recommendation.status == "LIVE")
            )
        ).scalars()
    }
    out: list[LiveFalsifierOut] = []
    if not recs:
        return out
    falsifiers = (
        (
            await session.execute(
                select(Falsifier).where(
                    Falsifier.recommendation_id.in_(recs),
                    Falsifier.breached_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for f in sorted(falsifiers, key=lambda f: (str(f.recommendation_id), str(f.id))):
        rec = recs[f.recommendation_id]
        obs = await observe(session, rec, f.field_id, as_of)
        out.append(
            LiveFalsifierOut(
                falsifier_id=str(f.id),
                recommendation_id=str(rec.id),
                isin=rec.isin,
                tradingsymbol=rec.tradingsymbol,
                horizon=rec.horizon,
                field_id=f.field_id,
                operator=f.operator,
                threshold=f.threshold,
                human_text=f.human_text,
                current_value=obs.value if obs else None,
                observed_as_of=obs.as_of.isoformat() if obs else None,
                breached=(
                    is_breached(f.operator, obs.value, obs.previous, f.threshold)
                    if obs
                    else None
                ),
            )
        )
    return out
