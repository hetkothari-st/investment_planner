"""Calibration scoring, sample gating, and deterministic verdicts."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from corpus.db.models import CalibrationResult, OhlcvDaily
from corpus.sim.calibration import (
    _verdict,
    calibration_summary,
    load_calibration_config,
    score_expired_recommendations,
)
from corpus.sim.theses import FalsifierIn, ManualThesisIn, create_manual_thesis

D = Decimal
CFG = load_calibration_config()
BENCH = CFG.benchmark_instrument_token


BASE_BAND = D("8")


def body(token: int, expires: date, base: Decimal = BASE_BAND) -> ManualThesisIn:
    return ManualThesisIn(
        isin=f"INE{token}X",
        instrument_token=token,
        horizon="MID",
        expires_on=expires,
        ref_price=D("100"),
        band_bear_pct=D("-10"),
        band_base_pct=base,
        band_bull_pct=D("20"),
        conviction="MODERATE",
        suggested_size_inr=D("10000"),
        thesis_md="A thesis with at least ten characters.",
        falsifiers=[
            FalsifierIn(
                field_id="price.close", operator="LT", threshold=D("85"),
                human_text="Price breaches the bear level",
            )
        ],
    )


async def test_thesis_requires_falsifier_and_ordered_bands():
    with pytest.raises(ValidationError):
        ManualThesisIn.model_validate(
            body(1, date(2027, 1, 1)).model_dump() | {"falsifiers": []}
        )
    with pytest.raises(ValidationError):
        ManualThesisIn.model_validate(
            body(1, date(2027, 1, 1)).model_dump()
            | {"band_bear_pct": "9", "band_base_pct": "8"}
        )


async def test_scoring_at_expiry(session):
    issued = date(2026, 1, 5)
    expires = date(2026, 7, 6)
    rec = await create_manual_thesis(session, body(555, expires), issued)

    # instrument: 100 -> 112 (in band, direction correct); index: 100 -> 106
    for token, start, end in ((555, D("100"), D("112")), (BENCH, D("100"), D("106"))):
        session.add(OhlcvDaily(instrument_token=token, trade_date=issued, close=start))
        session.add(
            OhlcvDaily(
                instrument_token=token, trade_date=expires - timedelta(days=1), close=end
            )
        )
    await session.commit()

    scored, skipped = await score_expired_recommendations(session, date(2026, 7, 31))
    assert (scored, skipped) == (1, [])

    r = (await session.execute(select(CalibrationResult))).scalar_one()
    assert r.actual_return_pct == D("12.0000")
    assert r.in_band is True
    assert r.direction_correct is True
    assert r.index_return_pct == D("6.0000")
    # MODERATE -> p=0.65; brier = (0.65-1)^2
    assert r.brier == D("0.12250")
    assert r.band_error_pct == D("4.0000")
    # net return: costs and LTCG shave the gross 12%
    assert D("9") < r.actual_net_return_pct < D("12")

    await session.refresh(rec)
    assert rec.status == "EXPIRED"

    # Scoring is idempotent: nothing is scored twice.
    scored_again, _ = await score_expired_recommendations(session, date(2026, 8, 31))
    assert scored_again == 0


async def test_scoring_skips_unpriceable(session):
    rec = await create_manual_thesis(
        session, body(777, date(2026, 7, 1)), date(2026, 1, 5)
    )
    scored, skipped = await score_expired_recommendations(session, date(2026, 7, 31))
    assert scored == 0
    assert "no OHLCV" in skipped[0]
    await session.refresh(rec)
    assert rec.status == "LIVE"  # not falsely expired without a score


async def test_sample_gating_below_twenty(session):
    issued, expires = date(2026, 1, 5), date(2026, 7, 6)
    session.add(OhlcvDaily(instrument_token=888, trade_date=issued, close=D("100")))
    session.add(OhlcvDaily(instrument_token=888, trade_date=expires, close=D("105")))
    await session.commit()
    await create_manual_thesis(session, body(888, expires), issued)
    await score_expired_recommendations(session, date(2026, 7, 31))

    summary = {s.horizon: s for s in await calibration_summary(session)}
    mid = summary["MID"]
    assert mid.n == 1
    assert mid.hit_rate_pct is None, "no rate below 20 scored calls"
    assert "1 of 20 scored calls needed" in mid.verdict
    assert summary["SHORT"].n == 0


def test_verdict_thresholds():
    v, sev = _verdict("SHORT", 41, D("44"), D("60"), D("-8.4"))
    assert sev == "failure"
    assert "not good at short-horizon calls" in v
    assert "-8.4%" in v

    v, sev = _verdict("MID", 63, D("61"), D("60"), D("3.2"))
    assert sev == "neutral"

    _, sev = _verdict("LONG", 30, D("55"), D("90"), None)
    assert sev == "warning"  # bands too wide

    _, sev = _verdict("LONG", 30, D("55"), D("35"), None)
    assert sev == "warning"  # bands are fantasy
