"""M6 acceptance: 20 consecutive generations with zero bare numerals and zero
unknown tokens; a deliberately broken composer yields a metrics-only report
and a cascade_gap row."""

from decimal import Decimal

from sqlalchemy import select

from corpus.db.models import CascadeGap
from corpus.llm.extract.extractor import ExtractionResult, QualFactOut, validate_spans
from corpus.research.contract import NUMERAL, TOKEN, strip_tokens
from corpus.research.report import assemble_report, render_value

D = Decimal

METRICS = {
    "fin.roce_median_5y": D("19.4321"),
    "val.pe_pctl_5y": D("31.07"),
    "gov.pledge_pct": D("2.145"),
}

FACT = QualFactOut(
    fact_type="CAPEX",
    direction="POSITIVE",
    magnitude_band="MATERIAL",
    horizon_relevance=["MID"],
    summary="Board approved brownfield capacity expansion at the existing site.",
    evidence_span="the Board has approved a brownfield expansion",
)


def good_composer(symbol, horizon, whitelist, facts, feedback):
    return f"""\
## Position
A {horizon} horizon thesis on {symbol}.

## Why now
Median ROCE is {{{{fin.roce_median_5y}}}} and the stock sits at the
{{{{val.pe_pctl_5y}}}} percentile of its own history. The board approved an
expansion [F1].

## What has to stay true
- Promoter pledge {{{{gov.pledge_pct}}}} stays low.

## How this loses money
The expansion [F1] overruns and absorbs cash. Pledged collateral
{{{{gov.pledge_pct}}}} triggers forced supply. A key customer walks.

## What we could not check
Estimate revisions are unavailable.
"""


def numeral_composer(symbol, horizon, whitelist, facts, feedback):
    return good_composer(symbol, horizon, whitelist, facts, feedback).replace(
        "Median ROCE is {{fin.roce_median_5y}}", "Median ROCE is 19.4%"
    )


async def test_twenty_consecutive_generations_zero_violations(session):
    for i in range(20):
        report = await assemble_report(
            session, good_composer, "INE000TEST01", f"SYM{i}", "MID",
            METRICS, [FACT], band_text="band", sizing_text="sizing", coverage=0.82,
        )
        assert report.narrative_included
        narrative = next(b for b in report.blocks if b.kind == "narrative")
        assert narrative.provenance == "INFERRED"
        # zero unresolved tokens, zero tokens left
        assert not TOKEN.search(narrative.content)
        # substituted values appear, rendered per registry
        assert "19.43%" in narrative.content

    gaps = (await session.execute(select(CascadeGap))).scalars().all()
    assert gaps == []


async def test_broken_prompt_falls_back_to_metrics_only(session):
    report = await assemble_report(
        session, numeral_composer, "INE000TEST01", "SYM", "MID",
        METRICS, [FACT], band_text="band", sizing_text="sizing", coverage=0.82,
    )
    assert report.narrative_included is False
    kinds = [b.kind for b in report.blocks]
    assert "narrative" not in kinds
    assert "metrics" in kinds and "band" in kinds  # deterministic blocks still render

    gaps = (await session.execute(select(CascadeGap))).scalars().all()
    assert len(gaps) == 2  # first attempt + the single retry, never more
    assert all(g.reason.startswith("BARE_NUMERAL") for g in gaps)
    assert gaps[0].raw_output and "19.4%" in gaps[0].raw_output


async def test_retry_once_recovers_when_feedback_fixes_it(session):
    calls = []

    def flaky(symbol, horizon, whitelist, facts, feedback):
        calls.append(feedback)
        if feedback is None:
            return numeral_composer(symbol, horizon, whitelist, facts, feedback)
        return good_composer(symbol, horizon, whitelist, facts, feedback)

    report = await assemble_report(
        session, flaky, "INE000TEST01", "SYM", "MID",
        METRICS, [FACT], band_text="b", sizing_text="s", coverage=0.8,
    )
    assert report.narrative_included
    assert calls == [None, "BARE_NUMERAL: 19.4"]
    gaps = (await session.execute(select(CascadeGap))).scalars().all()
    assert len(gaps) == 1  # the failed first attempt is logged


def test_render_value_units():
    assert render_value("fin.roce_median_5y", D("19.4321")) == "19.43%"
    assert render_value("risk.beta_1y", D("1.10")) == "1.1x"
    assert render_value("liq.adv_20d_inr", D("12.5")) == "₹12.5 cr"
    assert render_value("earn.days_to_next_result", D("12")) == "12 days"


def test_extraction_span_validation():
    source = "During the quarter, the Board has approved a brownfield expansion."
    result = ExtractionResult(
        facts=[
            FACT,
            QualFactOut(
                fact_type="GUIDANCE", direction="POSITIVE", magnitude_band="SMALL",
                horizon_relevance=["MID"], summary="Guidance raised.",
                evidence_span="guidance was raised to record levels",  # not in source
            ),
        ]
    )
    kept, discarded = validate_spans(result, source)
    assert [f.fact_type for f in kept] == ["CAPEX"]
    assert [f.fact_type for f in discarded] == ["GUIDANCE"]


def test_numeral_regex_sanity():
    assert NUMERAL.search(strip_tokens("worth {{fin.fcf_yield}} today")) is None
    assert NUMERAL.search("worth 12.5% today")
