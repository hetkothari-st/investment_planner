"""Pipeline step 6: compute metrics and persist metric_values / metric_gaps.

Metric functions are pure (corpus/metrics); this module is the caller that
loads raw rows and persists results. A metric that cannot be computed writes
a metric_gaps row with a reason — never a default.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from corpus.db.models import (
    Instrument,
    MetricGap,
    MetricValueRow,
    OhlcvDaily,
    Shareholding,
)
from corpus.db.upsert import upsert_rows
from corpus.metrics import governance, series
from corpus.metrics.registry import REGISTRY
from corpus.metrics.types import inputs_hash, q

# field_id -> (fn(bars) -> float|None). The single-series price family.
PRICE_FAMILY = {
    "price.close": series.last_close,
    "price.52w_high": series.high_52w,
    "price.52w_low": series.low_52w,
    "tech.dist_from_52w_high": series.dist_from_52w_high,
    "tech.dist_from_52w_low": series.dist_from_52w_low,
    "mom.ret_1m": lambda b: series.ret_window(b, series.D_1M),
    "mom.ret_3m": lambda b: series.ret_window(b, series.D_3M),
    "mom.ret_6m": lambda b: series.ret_window(b, series.D_6M),
    "mom.ret_12m_ex1m": lambda b: series.ret_window(b, series.D_1Y, skip=series.D_1M),
    "risk.vol_ann_1y": series.vol_ann_1y,
    "risk.max_dd_3y": series.max_dd_3y,
    "risk.downside_dev_1y": series.downside_dev_1y,
    "risk.ulcer_index_1y": series.ulcer_index_1y,
    "vol.volume_multiple": series.volume_multiple,
    "vol.obv_slope_3m": series.obv_slope_3m,
    "liq.adv_20d_inr": series.adv_20d_inr_cr,
    "liq.spread_bps_est": series.spread_bps_est,
    "liq.impact_cost_1l": series.impact_cost_1l,
}

# vs-benchmark family: fn(bars, benchmark_bars)
BENCH_FAMILY = {
    "mom.rs_1m": lambda b, x: series.relative_strength(b, x, series.D_1M),
    "mom.rs_3m": lambda b, x: series.relative_strength(b, x, series.D_3M),
    "mom.consistency_6m": series.consistency_6m,
    "risk.beta_1y": series.beta_1y,
}


async def load_bars(
    session: AsyncSession, instrument_token: int, as_of: date, max_days: int = 800
) -> list[series.Bar]:
    rows = (
        await session.execute(
            select(OhlcvDaily.adj_close, OhlcvDaily.close, OhlcvDaily.volume,
                   OhlcvDaily.high, OhlcvDaily.low)
            .where(
                OhlcvDaily.instrument_token == instrument_token,
                OhlcvDaily.trade_date <= as_of,
                OhlcvDaily.close.is_not(None),
            )
            .order_by(OhlcvDaily.trade_date.desc())
            .limit(max_days)
        )
    ).all()
    rows = list(reversed(rows))
    return [
        series.Bar(
            close=float(r.adj_close if r.adj_close is not None else r.close),
            volume=r.volume,
            high=float(r.high) if r.high is not None else None,
            low=float(r.low) if r.low is not None else None,
        )
        for r in rows
    ]


def _rows_for(
    isin: str, as_of: date, computed: dict[str, float | int | None], hash_: str
) -> tuple[list[dict], list[dict]]:
    values, gaps = [], []
    for field_id, raw in computed.items():
        spec = REGISTRY[field_id]
        if raw is None:
            gaps.append(
                {"isin": isin, "field_id": field_id, "as_of": as_of,
                 "reason": "INSUFFICIENT_HISTORY"}
            )
        else:
            values.append(
                {
                    "isin": isin,
                    "field_id": field_id,
                    "as_of": as_of,
                    "value": q(raw, spec.precision),
                    "unit": spec.unit,
                    "inputs_hash": hash_,
                }
            )
    return values, gaps


async def compute_symbol_metrics(
    session: AsyncSession,
    isin: str,
    instrument_token: int,
    benchmark_bars: list[series.Bar],
    as_of: date,
) -> tuple[int, int]:
    """Compute the OHLCV-derived families for one symbol. Returns (values, gaps)."""
    bars = await load_bars(session, instrument_token, as_of)
    hash_ = inputs_hash([instrument_token, as_of, len(bars),
                         bars[-1].close if bars else None])

    computed: dict[str, float | int | None] = {}
    for field_id, fn in PRICE_FAMILY.items():
        computed[field_id] = fn(bars)
    for field_id, fn in BENCH_FAMILY.items():
        computed[field_id] = fn(bars, benchmark_bars)

    # gov.* from shareholding when the source has data
    sh = (
        await session.execute(
            select(Shareholding)
            .where(Shareholding.isin == isin, Shareholding.period_end <= as_of)
            .order_by(Shareholding.period_end)
        )
    ).scalars().all()
    if sh:
        def series_of(attr: str) -> list[tuple[date, float]]:
            return [
                (r.period_end, float(getattr(r, attr)))
                for r in sh
                if getattr(r, attr) is not None
            ]

        computed["gov.promoter_pct"] = governance.latest(series_of("promoter_pct"))
        computed["gov.pledge_pct"] = governance.latest(series_of("promoter_pledged_pct"))
        computed["gov.pledge_trend_4q"] = governance.trend_4q(
            series_of("promoter_pledged_pct")
        )
        computed["gov.fii_pct"] = governance.latest(series_of("fii_pct"))
        computed["gov.fii_trend_4q"] = governance.trend_4q(series_of("fii_pct"))
        computed["gov.dii_trend_4q"] = governance.trend_4q(series_of("dii_pct"))

    values, gaps = _rows_for(isin, as_of, computed, hash_)
    n_values = await upsert_rows(
        session, MetricValueRow.__table__, values,
        key_cols=["isin", "field_id", "as_of"], skip_update_cols=("computed_at",),
    )
    await upsert_rows(
        session, MetricGap.__table__, gaps, key_cols=["isin", "field_id", "as_of"],
        skip_update_cols=(),
    )
    return n_values, len(gaps)


async def compute_universe_metrics(
    session: AsyncSession,
    as_of: date,
    benchmark_token: int,
) -> dict[str, int]:
    """Compute for every instrument with an ISIN in the universe tables."""
    benchmark_bars = await load_bars(session, benchmark_token, as_of)
    instruments = (
        await session.execute(
            select(Instrument.isin, Instrument.instrument_token)
            .where(Instrument.isin.is_not(None), Instrument.exchange == "NSE")
            .order_by(Instrument.isin)
        )
    ).all()
    totals = {"symbols": 0, "values": 0, "gaps": 0}
    for isin, token in instruments:
        v, g = await compute_symbol_metrics(session, isin, token, benchmark_bars, as_of)
        totals["symbols"] += 1
        totals["values"] += v
        totals["gaps"] += g
    await session.commit()
    return totals


async def load_metric_values(
    session: AsyncSession, as_of: date, field_ids: list[str]
) -> dict[str, dict[str, Decimal | None]]:
    """field_id -> {isin -> value} for the scoring layer."""
    rows = (
        await session.execute(
            select(MetricValueRow).where(
                MetricValueRow.as_of == as_of,
                MetricValueRow.field_id.in_(field_ids),
            )
        )
    ).scalars().all()
    out: dict[str, dict[str, Decimal | None]] = {f: {} for f in field_ids}
    for r in rows:
        out[r.field_id][r.isin] = r.value
    return out
