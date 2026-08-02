"""Nightly falsifier evaluation — docs/05, pipeline step 8.

Thesis-breakage alerts, not price alerts. On breach:
- `falsifiers.breached_at` is set (never cleared: a broken thesis stays broken)
- the recommendation flips to INVALIDATED (status is the one mutable column)
- an alert quotes the *original thesis line* the breach contradicts,
  verbatim from the frozen report_md
- any linked open sim position is flagged, NOT auto-closed — the close is
  the user's decision, and that decision is recorded and later scored

A falsifier whose current value cannot be resolved is skipped and reported
as a gap. Silence is never success.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from corpus.db.models import Alert, Falsifier, MetricValueRow, Recommendation, SimPosition
from corpus.sim.positions import last_close


@dataclass
class Observation:
    value: Decimal
    as_of: date
    previous: Decimal | None  # prior distinct as_of, for CROSSES_* operators


@dataclass
class CheckReport:
    as_of: date
    checked: int = 0
    breached: int = 0
    already_breached: int = 0
    skipped: list[str] = field(default_factory=list)  # human-readable gaps


async def observe(
    session: AsyncSession,
    rec: Recommendation,
    field_id: str,
    as_of: date,
) -> Observation | None:
    """Resolve the falsifier's current value. price.close reads the same
    OHLCV series the simulator marks against; everything else reads the
    metric spine at its latest compute date."""
    if field_id == "price.close":
        if rec.instrument_token is None:
            return None
        latest = await last_close(session, rec.instrument_token, as_of)
        if latest is None:
            return None
        prior = await last_close(session, rec.instrument_token, latest[0], strict=True)
        return Observation(
            value=latest[1], as_of=latest[0], previous=prior[1] if prior else None
        )

    rows = (
        await session.execute(
            select(MetricValueRow.as_of, MetricValueRow.value)
            .where(
                MetricValueRow.isin == rec.isin,
                MetricValueRow.field_id == field_id,
                MetricValueRow.as_of <= as_of,
                MetricValueRow.value.is_not(None),
            )
            .order_by(MetricValueRow.as_of.desc())
            .limit(2)
        )
    ).all()
    if not rows:
        return None
    return Observation(
        value=rows[0].value,
        as_of=rows[0].as_of,
        previous=rows[1].value if len(rows) > 1 else None,
    )


def is_breached(
    operator: str, current: Decimal, previous: Decimal | None, threshold: Decimal
) -> bool | None:
    """None means the operator cannot be evaluated (CROSSES_* without a
    prior observation) — reported as a gap, never treated as intact."""
    match operator:
        case "LT":
            return current < threshold
        case "LTE":
            return current <= threshold
        case "GT":
            return current > threshold
        case "GTE":
            return current >= threshold
        case "CROSSES_BELOW":
            if previous is None:
                return None
            return previous >= threshold and current < threshold
        case "CROSSES_ABOVE":
            if previous is None:
                return None
            return previous <= threshold and current > threshold
    raise ValueError(f"unknown operator {operator}")


def thesis_line_for(report_md: str, human_text: str) -> tuple[str, bool]:
    """The original thesis line this falsifier contradicts, quoted verbatim.
    Falls back to the falsifier's own text — flagged as not-found rather
    than silently pretending the thesis said it."""
    needle = human_text.strip()
    for line in report_md.splitlines():
        if needle and needle in line and line.strip():
            return line.strip(), True
    return needle, False


async def check_falsifiers(session: AsyncSession, as_of: date) -> CheckReport:
    report = CheckReport(as_of=as_of)
    live_recs = {
        r.id: r
        for r in (
            await session.execute(
                select(Recommendation).where(Recommendation.status == "LIVE")
            )
        ).scalars()
    }
    if not live_recs:
        return report
    falsifiers = (
        (
            await session.execute(
                select(Falsifier).where(
                    Falsifier.recommendation_id.in_(live_recs),
                    Falsifier.breached_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    for f in sorted(falsifiers, key=lambda f: (str(f.recommendation_id), str(f.id))):
        rec = live_recs[f.recommendation_id]
        report.checked += 1
        obs = await observe(session, rec, f.field_id, as_of)
        if obs is None:
            report.skipped.append(
                f"{rec.tradingsymbol or rec.isin} {f.field_id}: no value available"
            )
            continue
        verdict = is_breached(f.operator, obs.value, obs.previous, f.threshold)
        if verdict is None:
            report.skipped.append(
                f"{rec.tradingsymbol or rec.isin} {f.field_id}: {f.operator} needs "
                "a prior observation; only one exists"
            )
            continue
        if not verdict:
            continue

        report.breached += 1
        f.breached_at = now
        if rec.status == "LIVE":  # a second falsifier on the same thesis
            rec.status = "INVALIDATED"  # status-only: the immutability trigger allows it
        line, found = thesis_line_for(rec.report_md, f.human_text)
        session.add(
            Alert(
                kind="FALSIFIER_BREACH",
                falsifier_id=f.id,
                recommendation_id=rec.id,
                isin=rec.isin,
                tradingsymbol=rec.tradingsymbol,
                horizon=rec.horizon,
                field_id=f.field_id,
                operator=f.operator,
                threshold=f.threshold,
                observed_value=obs.value,
                observed_as_of=obs.as_of,
                thesis_line=line,
                thesis_line_found=found,
            )
        )
        open_positions = (
            (
                await session.execute(
                    select(SimPosition).where(
                        SimPosition.recommendation_id == rec.id,
                        SimPosition.closed_on.is_(None),
                        SimPosition.flagged_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        for pos in open_positions:
            pos.flagged_at = now
            pos.flag_reason = f"Falsifier breached: {f.human_text}"

    await session.commit()
    return report
