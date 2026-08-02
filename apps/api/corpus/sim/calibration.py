"""Calibration ledger — docs/08. Every recommendation is scored at expiry,
simulated or not. Verdicts are templated deterministic text with thresholds;
the system grading itself must not be able to spin.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache

import yaml
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from corpus.db.models import CalibrationResult, OhlcvDaily, Recommendation
from corpus.planner.assumptions import CONFIG_DIR
from corpus.sim.costs import buy_costs, load_cost_rates, sell_costs

PCT = Decimal("0.0001")


class CalibrationConfig(BaseModel):
    version: str
    conviction_probability: dict[str, Decimal]
    min_scored_for_display: int
    benchmark_instrument_token: int
    tax_short_pct: Decimal
    tax_long_pct: Decimal


@lru_cache
def load_calibration_config(version: str = "v1") -> CalibrationConfig:
    return CalibrationConfig.model_validate(
        yaml.safe_load((CONFIG_DIR / f"calibration.{version}.yaml").read_text())
    )


async def _close_on_or_before(
    session: AsyncSession, token: int, d: date
) -> Decimal | None:
    return (
        await session.execute(
            select(OhlcvDaily.close)
            .where(
                OhlcvDaily.instrument_token == token,
                OhlcvDaily.trade_date <= d,
                OhlcvDaily.close.is_not(None),
            )
            .order_by(OhlcvDaily.trade_date.desc())
            .limit(1)
        )
    ).scalar()


def net_return_pct(
    ref_price: Decimal, exit_price: Decimal, horizon: str, cfg: CalibrationConfig
) -> Decimal:
    """Return after modelled round-trip costs and tax on a notional 1-lot-like
    position of 100 shares — cost fractions are scale-invariant except the
    flat DP charge, which is deliberately included: small trades should look
    as expensive as they are."""
    qty = 100
    rates = load_cost_rates()
    entry_cost = buy_costs(ref_price, qty, rates).total
    exit_cost = sell_costs(exit_price, qty, rates).total
    gross = qty * (exit_price - ref_price)
    pre_tax = gross - entry_cost - exit_cost
    tax_rate = (
        cfg.tax_short_pct if horizon == "SHORT" else cfg.tax_long_pct
    ) / 100
    tax = pre_tax * tax_rate if pre_tax > 0 else Decimal(0)
    return ((pre_tax - tax) / (qty * ref_price) * 100).quantize(PCT, ROUND_HALF_UP)


def score_one(
    rec: Recommendation,
    exit_price: Decimal,
    index_return: Decimal | None,
    scored_on: date,
    cfg: CalibrationConfig,
) -> CalibrationResult:
    actual = ((exit_price / rec.ref_price - 1) * 100).quantize(PCT, ROUND_HALF_UP)
    direction_correct = (actual >= 0) == (rec.band_base_pct >= 0)
    p = cfg.conviction_probability[rec.conviction]
    outcome = Decimal(1) if direction_correct else Decimal(0)
    return CalibrationResult(
        recommendation_id=rec.id,
        scored_on=scored_on,
        actual_return_pct=actual,
        actual_net_return_pct=net_return_pct(
            rec.ref_price, exit_price, rec.horizon, cfg
        ),
        index_return_pct=index_return,
        in_band=rec.band_bear_pct <= actual <= rec.band_bull_pct,
        direction_correct=direction_correct,
        brier=((p - outcome) ** 2).quantize(Decimal("0.00001")),
        band_error_pct=abs(actual - rec.band_base_pct).quantize(PCT),
        calibration_version=cfg.version,
    )


async def score_expired_recommendations(
    session: AsyncSession, as_of: date
) -> tuple[int, list[str]]:
    """Pipeline step 10. Returns (scored_count, skipped_reasons)."""
    cfg = load_calibration_config()
    already = select(CalibrationResult.recommendation_id)
    due = (
        (
            await session.execute(
                select(Recommendation).where(
                    Recommendation.expires_on <= as_of,
                    Recommendation.id.not_in(already),
                )
            )
        )
        .scalars()
        .all()
    )
    skipped: list[str] = []
    scored = 0
    for rec in due:
        if rec.instrument_token is None:
            skipped.append(f"{rec.isin}: no instrument token, cannot price expiry")
            continue
        exit_price = await _close_on_or_before(
            session, rec.instrument_token, rec.expires_on
        )
        if exit_price is None:
            skipped.append(f"{rec.isin}: no OHLCV at expiry {rec.expires_on}")
            continue
        index_return = None
        idx_start = await _close_on_or_before(
            session, cfg.benchmark_instrument_token, rec.issued_at.date()
        )
        idx_end = await _close_on_or_before(
            session, cfg.benchmark_instrument_token, rec.expires_on
        )
        if idx_start and idx_end:
            index_return = ((idx_end / idx_start - 1) * 100).quantize(PCT)
        session.add(score_one(rec, exit_price, index_return, as_of, cfg))
        if rec.status == "LIVE":
            rec.status = "EXPIRED"
        scored += 1
    await session.commit()
    return scored, skipped


class HorizonSummary(BaseModel):
    horizon: str
    n: int
    n_needed: int
    hit_rate_pct: Decimal | None       # None until the sample gate opens
    band_coverage_pct: Decimal | None
    mean_brier: Decimal | None
    net_alpha_pct: Decimal | None
    verdict: str
    severity: str  # neutral | warning | failure


async def calibration_summary(session: AsyncSession) -> list[HorizonSummary]:
    cfg = load_calibration_config()
    rows = (
        await session.execute(
            select(CalibrationResult, Recommendation.horizon).join(
                Recommendation, Recommendation.id == CalibrationResult.recommendation_id
            )
        )
    ).all()
    out = []
    for horizon in ("SHORT", "MID", "LONG"):
        results = [r for r, h in rows if h == horizon]
        n = len(results)
        if n < cfg.min_scored_for_display:
            out.append(
                HorizonSummary(
                    horizon=horizon,
                    n=n,
                    n_needed=cfg.min_scored_for_display,
                    hit_rate_pct=None,
                    band_coverage_pct=None,
                    mean_brier=None,
                    net_alpha_pct=None,
                    verdict=(
                        f"{horizon} — {n} of {cfg.min_scored_for_display} scored calls "
                        "needed. Uncalibrated: small-sample hit rates are actively "
                        "misleading."
                    ),
                    severity="neutral",
                )
            )
            continue
        hit = Decimal(sum(1 for r in results if r.direction_correct)) / n * 100
        coverage = Decimal(sum(1 for r in results if r.in_band)) / n * 100
        brier = sum((r.brier or Decimal(0)) for r in results) / n
        with_index = [r for r in results if r.index_return_pct is not None]
        alpha = (
            sum((r.actual_net_return_pct - r.index_return_pct) for r in with_index)
            / len(with_index)
            if with_index
            else None
        )
        verdict, severity = _verdict(horizon, n, hit, coverage, alpha)
        out.append(
            HorizonSummary(
                horizon=horizon,
                n=n,
                n_needed=cfg.min_scored_for_display,
                hit_rate_pct=hit.quantize(Decimal("0.1")),
                band_coverage_pct=coverage.quantize(Decimal("0.1")),
                mean_brier=brier.quantize(Decimal("0.001")),
                net_alpha_pct=alpha.quantize(Decimal("0.1")) if alpha is not None else None,
                verdict=verdict,
                severity=severity,
            )
        )
    return out


def _verdict(
    horizon: str, n: int, hit: Decimal, coverage: Decimal, alpha: Decimal | None
) -> tuple[str, str]:
    """Deterministic thresholds. No prose model gets near this."""
    alpha_txt = (
        f" Net of costs, {'+' if alpha >= 0 else ''}{alpha.quantize(Decimal('0.1'))}% "
        "against the index."
        if alpha is not None
        else ""
    )
    base = (
        f"{horizon} — direction correct {hit.quantize(Decimal('1'))}% of {n} scored "
        f"calls.{alpha_txt}"
    )
    if hit < 50:
        return (
            base + f" This system is not good at {horizon.lower()}-horizon calls. "
            "Suggested action: stop acting on them, or reduce sizing to research-only.",
            "failure",
        )
    if coverage > 85:
        return (
            base + f" Band coverage {coverage.quantize(Decimal('1'))}% — bands this "
            "wide are too easy to hit to be useful.",
            "warning",
        )
    if coverage < 40:
        return (
            base + f" Band coverage {coverage.quantize(Decimal('1'))}% — the bands "
            "are fantasy.",
            "warning",
        )
    return base, "neutral"
