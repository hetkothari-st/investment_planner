"""Report assembly — docs/07.

Numbers are computed, prose is written. The composer produces a draft with
{{tokens}}; the validator gates it; the renderer substitutes real values.
On violation: log to cascade_gap, retry once with the violation appended to
the prompt, and on second failure render the report WITHOUT the narrative —
a report with no prose is fine; a report with invented prose is not.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from corpus.db.models import CascadeGap
from corpus.llm.compose.composer import Composer
from corpus.llm.extract.extractor import QualFactOut
from corpus.metrics.registry import REGISTRY
from corpus.research.contract import ContractViolation, substitute_tokens, validate


@dataclass(frozen=True)
class ReportBlock:
    provenance: str  # MEASURED | COMPUTED | INFERRED | SOURCE
    kind: str        # narrative | metrics | band | sizing | coverage
    content: str


@dataclass(frozen=True)
class Report:
    isin: str
    horizon: str
    blocks: tuple[ReportBlock, ...]
    narrative_included: bool
    coverage: float


def render_value(field_id: str, value: Decimal | float) -> str:
    """Human rendering for token substitution, per registry unit/precision."""
    spec = REGISTRY[field_id]
    v = float(value)
    body = f"{v:,.{min(spec.precision, 2)}f}".rstrip("0").rstrip(".")
    match spec.unit:
        case "pct":
            return f"{body}%"
        case "x":
            return f"{body}x"
        case "inr":
            return f"₹{body}"
        case "inr_cr":
            return f"₹{body} cr"
        case "days":
            return f"{body} days"
        case _:
            return body


async def compose_narrative(
    session: AsyncSession,
    composer: Composer,
    isin: str,
    symbol: str,
    horizon: str,
    metric_values: dict[str, Decimal | float],
    facts: list[QualFactOut],
) -> tuple[str | None, list[str]]:
    """Returns (rendered narrative or None, violation log). Never raises on
    contract violations — the failure path is data, not an exception."""
    whitelist = {
        fid: f"{REGISTRY[fid].label} ({REGISTRY[fid].unit})" for fid in metric_values
    }
    fact_ids = set(range(1, len(facts) + 1))
    violations: list[str] = []
    feedback: str | None = None

    for _attempt in (1, 2):  # retry once, never more (docs/07)
        draft = composer(symbol, horizon, whitelist, facts, feedback)
        try:
            validate(draft, set(whitelist), fact_ids)
            rendered = substitute_tokens(
                draft, {fid: render_value(fid, v) for fid, v in metric_values.items()}
            )
            return rendered, violations
        except ContractViolation as v:
            violations.append(str(v))
            session.add(
                CascadeGap(
                    stage="compose",
                    isin=isin,
                    horizon=horizon,
                    reason=str(v),
                    raw_output=draft,
                )
            )
            feedback = str(v)
    await session.commit()
    return None, violations


async def assemble_report(
    session: AsyncSession,
    composer: Composer,
    isin: str,
    symbol: str,
    horizon: str,
    metric_values: dict[str, Decimal | float],
    facts: list[QualFactOut],
    band_text: str,
    sizing_text: str,
    coverage: float,
) -> Report:
    narrative, _ = await compose_narrative(
        session, composer, isin, symbol, horizon, metric_values, facts
    )
    blocks: list[ReportBlock] = []
    if narrative is not None:
        blocks.append(ReportBlock("INFERRED", "narrative", narrative))
    metrics_md = "\n".join(
        f"| {REGISTRY[fid].label} | {render_value(fid, v)} |"
        for fid, v in sorted(metric_values.items())
    )
    blocks.append(
        ReportBlock("MEASURED", "metrics", f"| Metric | Value |\n|---|---|\n{metrics_md}")
    )
    blocks.append(ReportBlock("COMPUTED", "band", band_text))
    blocks.append(ReportBlock("COMPUTED", "sizing", sizing_text))
    for f in facts:
        if f.evidence_span:
            blocks.append(ReportBlock("SOURCE", "evidence", f.evidence_span))
    return Report(
        isin=isin,
        horizon=horizon,
        blocks=tuple(blocks),
        narrative_included=narrative is not None,
        coverage=coverage,
    )
