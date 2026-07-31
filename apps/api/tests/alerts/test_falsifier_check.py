"""M8 acceptance: synthetically breach a falsifier → the alert quotes the
correct original thesis line, the recommendation flips to INVALIDATED, and
the linked position is flagged but NOT auto-closed. Re-running the check
raises nothing new."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from corpus.db.models import (
    Alert,
    Falsifier,
    MetricValueRow,
    OhlcvDaily,
    Recommendation,
    SimPosition,
)
from corpus.sim.falsifiers import check_falsifiers, is_breached, thesis_line_for
from corpus.sim.positions import open_simulated
from corpus.sim.theses import FalsifierIn, ManualThesisIn, create_manual_thesis

D = Decimal
TODAY = date(2026, 7, 31)
ISSUED = TODAY - timedelta(days=30)

PLEDGE_TEXT = "Promoter pledge stays below 15% of holding"
THESIS_MD = f"""## Position
A MID horizon thesis on TESTCO.

## What has to stay true
- {PLEDGE_TEXT}, as it has for six years.
- Margin trajectory holds.

## How this loses money
Pledged collateral triggers forced supply.
"""


def thesis(token=777, falsifiers=None) -> ManualThesisIn:
    return ManualThesisIn(
        isin="INE000ALERT1",
        tradingsymbol="TESTCO",
        instrument_token=token,
        horizon="MID",
        expires_on=TODAY + timedelta(days=180),
        ref_price=D("500"),
        band_bear_pct=D("-15"),
        band_base_pct=D("12"),
        band_bull_pct=D("30"),
        conviction="MODERATE",
        suggested_size_inr=D("100000"),
        thesis_md=THESIS_MD,
        falsifiers=falsifiers
        or [
            FalsifierIn(
                field_id="gov.pledge_pct",
                operator="GT",
                threshold=D("15"),
                human_text=PLEDGE_TEXT,
            )
        ],
    )


def metric(value, as_of=TODAY, field_id="gov.pledge_pct"):
    return MetricValueRow(
        isin="INE000ALERT1",
        field_id=field_id,
        as_of=as_of,
        value=D(str(value)),
        unit="pct",
        inputs_hash="test",
    )


async def test_breach_flow_end_to_end(session):
    rec = await create_manual_thesis(session, thesis(), ISSUED)
    session.add(OhlcvDaily(instrument_token=777, trade_date=ISSUED, close=D("500")))
    await session.commit()
    position = await open_simulated(session, rec.id, D("50000"), ISSUED)

    # intact: pledge at 12 — no breach, nothing raised
    session.add(metric(12, as_of=TODAY - timedelta(days=1)))
    await session.commit()
    report = await check_falsifiers(session, TODAY)
    assert (report.checked, report.breached) == (1, 0)
    assert (await session.execute(select(Alert))).scalars().all() == []

    # the synthetic breach: pledge jumps to 18 against the GT-15 falsifier
    session.add(metric(18))
    await session.commit()
    report = await check_falsifiers(session, TODAY)
    assert report.breached == 1

    # the alert quotes the ORIGINAL thesis line, verbatim
    alert = (await session.execute(select(Alert))).scalar_one()
    assert alert.thesis_line == f"- {PLEDGE_TEXT}, as it has for six years."
    assert alert.thesis_line_found is True
    assert alert.observed_value == D("18")
    assert alert.threshold == D("15")

    # the recommendation flipped to INVALIDATED (through the immutability
    # trigger's one permitted column)
    fresh_rec = await session.get(Recommendation, rec.id, populate_existing=True)
    assert fresh_rec.status == "INVALIDATED"
    breached_f = (await session.execute(select(Falsifier))).scalar_one()
    assert breached_f.breached_at is not None

    # the position is flagged, NOT closed
    fresh_pos = await session.get(SimPosition, position.id, populate_existing=True)
    assert fresh_pos.flagged_at is not None
    assert PLEDGE_TEXT in (fresh_pos.flag_reason or "")
    assert fresh_pos.closed_on is None

    # idempotent: nothing left to check, no duplicate alert
    report = await check_falsifiers(session, TODAY)
    assert (report.checked, report.breached) == (0, 0)
    assert len((await session.execute(select(Alert))).scalars().all()) == 1


async def test_unresolvable_falsifier_is_a_reported_gap_not_success(session):
    await create_manual_thesis(session, thesis(), ISSUED)
    report = await check_falsifiers(session, TODAY)  # no metric rows at all
    assert report.checked == 1
    assert report.breached == 0
    assert len(report.skipped) == 1
    assert "no value available" in report.skipped[0]


async def test_price_close_falsifier_reads_ohlcv(session):
    body = thesis(
        falsifiers=[
            FalsifierIn(
                field_id="price.close",
                operator="LT",
                threshold=D("425"),  # bear level
                human_text="Price holds above the bear-case level of 425",
            )
        ]
    )
    rec = await create_manual_thesis(session, body, ISSUED)
    session.add(OhlcvDaily(instrument_token=777, trade_date=TODAY, close=D("410")))
    await session.commit()
    report = await check_falsifiers(session, TODAY)
    assert report.breached == 1
    fresh = await session.get(Recommendation, rec.id, populate_existing=True)
    assert fresh.status == "INVALIDATED"


async def test_crosses_below_needs_a_prior_observation(session):
    body = thesis(
        falsifiers=[
            FalsifierIn(
                field_id="earn.revision_3m",
                operator="CROSSES_BELOW",
                threshold=D("0"),
                human_text="Consensus estimates stay positive",
            )
        ]
    )
    await create_manual_thesis(session, body, ISSUED)
    session.add(metric(-2, field_id="earn.revision_3m"))
    await session.commit()
    report = await check_falsifiers(session, TODAY)  # only one observation
    assert report.breached == 0
    assert "needs" in report.skipped[0]

    # a prior positive value arrives: now it genuinely crossed below
    session.add(metric(1, as_of=TODAY - timedelta(days=7), field_id="earn.revision_3m"))
    await session.commit()
    report = await check_falsifiers(session, TODAY)
    assert report.breached == 1


def test_operator_semantics():
    assert is_breached("LT", D("9"), None, D("10")) is True
    assert is_breached("LT", D("10"), None, D("10")) is False
    assert is_breached("LTE", D("10"), None, D("10")) is True
    assert is_breached("GT", D("11"), None, D("10")) is True
    assert is_breached("GTE", D("10"), None, D("10")) is True
    assert is_breached("CROSSES_BELOW", D("9"), None, D("10")) is None
    assert is_breached("CROSSES_BELOW", D("9"), D("11"), D("10")) is True
    assert is_breached("CROSSES_BELOW", D("8"), D("9"), D("10")) is False  # already below
    assert is_breached("CROSSES_ABOVE", D("11"), D("9"), D("10")) is True
    assert is_breached("CROSSES_ABOVE", D("12"), D("11"), D("10")) is False


def test_thesis_line_quoting():
    line, found = thesis_line_for(THESIS_MD, PLEDGE_TEXT)
    assert found and line == f"- {PLEDGE_TEXT}, as it has for six years."
    # honest fallback when the frozen thesis never contained the text
    line, found = thesis_line_for(THESIS_MD, "some text never written down")
    assert not found and line == "some text never written down"
