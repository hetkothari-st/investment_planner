"""Scenario bands from empirical quantiles — docs/05. Not from an LLM.

The band is the p20/p50/p80 of the stock's own realised forward-return
distribution, blended toward the sector's by shrinkage. If the p20 is -18%,
the report says -18%.

Conditioning on historical composite-score deciles needs a history of stored
scores; until enough accumulate (the pipeline persists them from now on), the
unconditioned distribution is used and n_analogues reflects that honestly.
"""

from dataclasses import dataclass

MIN_ANALOGUES = 30
SHRINK_K = 60  # lam = n / (n + K): 60 own-windows weighs the stock ~50/50


@dataclass(frozen=True)
class Band:
    bear_pct: float
    base_pct: float
    bull_pct: float
    n_analogues: int
    conditioned: bool  # False = fell back to the unconditioned distribution


def rolling_forward_returns(closes: list[float], horizon_days: int) -> list[float]:
    """Forward return (pct) of every window of `horizon_days` in the series."""
    if len(closes) <= horizon_days:
        return []
    return [
        (closes[i + horizon_days] / closes[i] - 1) * 100
        for i in range(len(closes) - horizon_days)
        if closes[i] > 0
    ]


def quantile(sorted_vals: list[float], p: float) -> float:
    """Linear-interpolated quantile on a pre-sorted list."""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    pos = p * (n - 1)
    lo = int(pos)
    frac = pos - lo
    if lo + 1 >= n:
        return sorted_vals[-1]
    return sorted_vals[lo] * (1 - frac) + sorted_vals[lo + 1] * frac


def scenario_band(
    own_returns: list[float],
    sector_returns: list[float],
    conditioned_returns: list[float] | None = None,
) -> Band | None:
    """p20/p50/p80, shrunk toward the sector distribution.

    conditioned_returns: windows where the stock's historical composite decile
    matched today's — used when >= MIN_ANALOGUES exist, else fall back.
    """
    conditioned = False
    dist = own_returns
    if conditioned_returns is not None and len(conditioned_returns) >= MIN_ANALOGUES:
        dist = conditioned_returns
        conditioned = True
    if not dist:
        return None

    n = len(dist)
    lam = n / (n + SHRINK_K)
    own_sorted = sorted(dist)
    quantiles = []
    for p in (0.20, 0.50, 0.80):
        own_q = quantile(own_sorted, p)
        if sector_returns:
            sector_q = quantile(sorted(sector_returns), p)
            quantiles.append(lam * own_q + (1 - lam) * sector_q)
        else:
            quantiles.append(own_q)
    bear, base, bull = quantiles
    if not (bear < base < bull):
        # Degenerate distribution (e.g. constant prices): no honest band exists.
        return None
    return Band(
        bear_pct=round(bear, 3),
        base_pct=round(base, 3),
        bull_pct=round(bull, 3),
        n_analogues=n,
        conditioned=conditioned,
    )
