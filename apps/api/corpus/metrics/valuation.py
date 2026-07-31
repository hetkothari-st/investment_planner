"""val.* — valuation, always as a percentile of own history (docs/06).

Absolute P/E is meaningless across sectors; percentiles are comparable.
Percentile metrics require full history — below min_history the answer is
None, never a partial percentile.
"""

D_5Y, D_10Y = 1260, 2520


def percentile_of_last(history: list[float], min_n: int) -> float | None:
    """Percentile rank (0-100) of the latest value within its own history."""
    if len(history) < min_n:
        return None
    current = history[-1]
    below = sum(1 for v in history if v < current)
    equal = sum(1 for v in history if v == current)
    return (below + 0.5 * equal) / len(history) * 100


def ratio_history(
    prices: list[float], denominator_per_share: list[float]
) -> list[float] | None:
    """Daily ratio series (e.g. P/E) from aligned price and per-share series.
    Non-positive denominators drop the day rather than fabricate a ratio."""
    if len(prices) != len(denominator_per_share):
        return None
    return [p / d for p, d in zip(prices, denominator_per_share, strict=True) if d > 0]


def pe_ttm(price: float | None, eps_ttm: float | None) -> float | None:
    if price is None or eps_ttm is None or eps_ttm <= 0:
        return None
    return price / eps_ttm


def earnings_yield_spread(
    pe: float | None, gsec_10y_pct: float | None
) -> float | None:
    """Earnings yield minus the 10-year G-sec — the one absolute valuation
    measure worth keeping."""
    if pe is None or pe <= 0 or gsec_10y_pct is None:
        return None
    return 100 / pe - gsec_10y_pct
