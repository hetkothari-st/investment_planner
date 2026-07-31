"""Research routes: candidate lists (deterministic, precomputed) and
on-demand report generation (the only place an LLM is ever awaited).

Rule (docs/01): the user never waits on an LLM call for a list.
"""

import os
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from corpus.db.models import Instrument, MetricValueRow, QualFact
from corpus.db.session import get_session
from corpus.llm.extract.extractor import QualFactOut
from corpus.research.compute import load_metric_values
from corpus.research.report import Report, assemble_report
from corpus.research.scoring import composite_scores, load_weights

router = APIRouter(prefix="/research", tags=["research"])

MIN_REPORT_COVERAGE = 0.60


class CandidateOut(BaseModel):
    isin: str
    tradingsymbol: str | None
    composite_pctl: float
    coverage: float
    conviction: str


class CandidatesOut(BaseModel):
    horizon: str
    as_of: str | None
    candidates: list[CandidateOut]
    message: str | None


@router.get("/candidates")
async def candidates(
    horizon: str = "MID", session: AsyncSession = Depends(get_session)
) -> CandidatesOut:
    """Deterministic ranking from stored metric_values. Empty is a valid,
    explained result — not a failure state."""
    if horizon not in ("SHORT", "MID", "LONG"):
        raise HTTPException(422, "horizon must be SHORT, MID or LONG")
    latest = await session.scalar(select(func.max(MetricValueRow.as_of)))
    if latest is None:
        return CandidatesOut(
            horizon=horizon, as_of=None, candidates=[],
            message=(
                "No metrics computed yet. Run the backfill and the nightly "
                "compute; candidates come from the deterministic spine."
            ),
        )
    weights = load_weights()[horizon]
    values = await load_metric_values(session, latest, list(weights))
    float_values = {
        f: {i: (float(v) if v is not None else None) for i, v in per.items()}
        for f, per in values.items()
    }
    sectors: dict[str, str] = {}
    scores = composite_scores(horizon, float_values, sectors)
    symbols = {
        i.isin: i.tradingsymbol
        for i in (await session.execute(select(Instrument))).scalars()
        if i.isin
    }
    ranked = sorted(scores, key=lambda s: (-s.composite_pctl, s.isin))[:20]
    return CandidatesOut(
        horizon=horizon,
        as_of=latest.isoformat(),
        candidates=[
            CandidateOut(
                isin=s.isin,
                tradingsymbol=symbols.get(s.isin),
                composite_pctl=round(s.composite_pctl, 2),
                coverage=round(s.coverage, 4),
                conviction="LOW" if s.coverage < 0.70 else "MODERATE",
            )
            for s in ranked
        ],
        message=None if ranked else (
            "No names scored for this horizon at the latest compute date."
        ),
    )


class ReportRequest(BaseModel):
    isin: str
    horizon: str


class BlockOut(BaseModel):
    provenance: str
    kind: str
    content: str


class ReportOut(BaseModel):
    isin: str
    horizon: str
    narrative_included: bool
    coverage: float
    blocks: list[BlockOut]


@router.post("/reports")
async def generate_report(
    body: ReportRequest, session: AsyncSession = Depends(get_session)
) -> ReportOut:
    """On-demand report generation — 20-60s when the LLM is wired. Refuses
    below 60% coverage (docs/07 anti-patterns) and without an API key."""
    if not (os.environ.get("ANTHROPIC_API_KEY") or ""):
        raise HTTPException(
            503,
            "ANTHROPIC_API_KEY is not configured. Reports need the composition "
            "model; everything deterministic still works without it.",
        )
    latest = await session.scalar(
        select(func.max(MetricValueRow.as_of)).where(MetricValueRow.isin == body.isin)
    )
    if latest is None:
        raise HTTPException(404, f"No metrics computed for {body.isin}.")
    rows = (
        await session.execute(
            select(MetricValueRow).where(
                MetricValueRow.isin == body.isin,
                MetricValueRow.as_of == latest,
                MetricValueRow.value.is_not(None),
            )
        )
    ).scalars().all()
    metric_values: dict[str, Decimal] = {r.field_id: r.value for r in rows}
    coverage = min(1.0, len(metric_values) / 22)  # against the OHLCV-family count
    if coverage < MIN_REPORT_COVERAGE:
        raise HTTPException(
            409,
            f"Coverage {coverage:.0%} is below the 60% floor. The report would "
            "be mostly dashes; refusing rather than degrading silently.",
        )
    facts = [
        QualFactOut(
            fact_type=f.fact_type,
            direction=f.direction or "NEUTRAL",
            magnitude_band=f.magnitude_band or "SMALL",
            horizon_relevance=["MID"],
            summary=f.summary,
            evidence_span=(f.evidence_span or "")[:400],
        )
        for f in (
            await session.execute(
                select(QualFact).where(QualFact.isin == body.isin).limit(8)
            )
        ).scalars()
    ]
    from corpus.llm.compose.composer import anthropic_composer

    symbol = (
        await session.scalar(
            select(Instrument.tradingsymbol).where(Instrument.isin == body.isin)
        )
    ) or body.isin
    report: Report = await assemble_report(
        session, anthropic_composer(), body.isin, symbol, body.horizon,
        metric_values, facts,
        band_text="Band computation joins in the nightly pipeline output.",
        sizing_text="Sizing joins once a corpus figure is present in the plan.",
        coverage=coverage,
    )
    return ReportOut(
        isin=report.isin,
        horizon=report.horizon,
        narrative_included=report.narrative_included,
        coverage=report.coverage,
        blocks=[
            BlockOut(provenance=b.provenance, kind=b.kind, content=b.content)
            for b in report.blocks
        ],
    )
