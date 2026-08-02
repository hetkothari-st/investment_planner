"""Composite scoring — docs/05.

Cross-sectional percentile within sector, winsorised at 2/98. Never raw
z-scores: Indian small-cap fundamentals have vicious outliers. Weights come
from versioned YAML; every score records weights_version.
"""

from dataclasses import dataclass
from functools import lru_cache

import yaml

from corpus.planner.assumptions import CONFIG_DIR

Horizon = str  # SHORT | MID | LONG


@lru_cache
def load_weights(version: str = "v1") -> dict:
    doc = yaml.safe_load((CONFIG_DIR / f"weights.{version}.yaml").read_text())
    return doc


def winsorise(values: list[float], lo_pct: float = 2, hi_pct: float = 98) -> list[float]:
    """Clamp to the 2nd/98th percentile of the cross-section."""
    if not values:
        return values
    ordered = sorted(values)
    n = len(ordered)
    lo = ordered[max(0, min(n - 1, int(n * lo_pct / 100)))]
    hi = ordered[max(0, min(n - 1, int(n * hi_pct / 100)))]
    return [min(hi, max(lo, v)) for v in values]


def cross_sectional_percentiles(values: dict[str, float | None]) -> dict[str, float]:
    """isin -> percentile (0-100) among the non-None cross-section, winsorised.
    Ties share a midrank so the result is order-independent."""
    present = {k: v for k, v in values.items() if v is not None}
    if not present:
        return {}
    keys = sorted(present)  # deterministic
    wins = winsorise([present[k] for k in keys])
    out: dict[str, float] = {}
    for key, val in zip(keys, wins, strict=True):
        below = sum(1 for v in wins if v < val)
        equal = sum(1 for v in wins if v == val)
        out[key] = (below + 0.5 * equal) / len(wins) * 100
    return out


@dataclass(frozen=True)
class CompositeScore:
    isin: str
    horizon: Horizon
    composite_pctl: float
    coverage: float  # fraction of weighted metrics computable
    weights_version: str
    metric_pctls: dict[str, float]  # field_id -> sector percentile used


def composite_scores(
    horizon: Horizon,
    metric_values: dict[str, dict[str, float | None]],
    sectors: dict[str, str],
    weights_version: str = "v1",
) -> list[CompositeScore]:
    """metric_values: field_id -> {isin -> value|None}.

    Percentiles are computed within each sector's cross-section, weighted per
    the horizon's config (negative weight = lower is better), then the raw
    weighted sums are re-ranked into a composite percentile across the
    universe. Coverage is the |weight| fraction actually computable per name.
    """
    cfg = load_weights(weights_version)
    weights: dict[str, float] = cfg[horizon]
    total_weight = sum(abs(w) for w in weights.values())

    # sector-bucketed percentiles per metric
    pctls: dict[str, dict[str, float]] = {}
    for field_id in weights:
        by_sector: dict[str, dict[str, float | None]] = {}
        for isin, value in metric_values.get(field_id, {}).items():
            by_sector.setdefault(sectors.get(isin, "UNKNOWN"), {})[isin] = value
        merged: dict[str, float] = {}
        for sector_values in by_sector.values():
            merged |= cross_sectional_percentiles(sector_values)
        pctls[field_id] = merged

    raw: dict[str, float] = {}
    coverage: dict[str, float] = {}
    used: dict[str, dict[str, float]] = {}
    isins = sorted({i for field in metric_values.values() for i in field})
    for isin in isins:
        score = 0.0
        covered = 0.0
        used[isin] = {}
        for field_id, weight in weights.items():
            pctl = pctls.get(field_id, {}).get(isin)
            if pctl is None:
                continue
            # negative weight: cheap/low is good — invert the percentile
            effective = pctl if weight >= 0 else 100 - pctl
            score += abs(weight) * effective
            covered += abs(weight)
            used[isin][field_id] = pctl
        raw[isin] = score / covered if covered else 0.0
        coverage[isin] = covered / total_weight if total_weight else 0.0

    composite_pctl = cross_sectional_percentiles(
        {i: raw[i] for i in isins if coverage[i] > 0}
    )
    return [
        CompositeScore(
            isin=isin,
            horizon=horizon,
            composite_pctl=composite_pctl.get(isin, 0.0),
            coverage=coverage[isin],
            weights_version=cfg["version"],
            metric_pctls=used[isin],
        )
        for isin in isins
    ]


def conviction(composite_pctl: float, coverage: float) -> str:
    """Low coverage caps conviction: a stock with missing fundamentals cannot
    be HIGH conviction no matter how good its momentum looks."""
    if composite_pctl >= 90 and coverage >= 0.85:
        return "HIGH"
    if composite_pctl >= 75 and coverage >= 0.70:
        return "MODERATE"
    return "LOW"
