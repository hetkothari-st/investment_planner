"""gov.* — shareholding and filings-derived governance metrics."""

from datetime import date

Series = list[tuple[date, float]]


def latest(series: Series | None) -> float | None:
    return series[-1][1] if series else None


def trend_4q(series: Series | None) -> float | None:
    """OLS slope over the last 4 quarterly observations, pp per quarter."""
    if series is None or len(series) < 4:
        return None
    vals = [v for _, v in series[-4:]]
    n = len(vals)
    xbar = (n - 1) / 2
    ybar = sum(vals) / n
    num = sum((i - xbar) * (y - ybar) for i, y in enumerate(vals))
    den = sum((i - xbar) ** 2 for i in range(n))
    return num / den


def auditor_changes_24m(change_dates: list[date], as_of: date) -> int:
    cutoff = as_of.toordinal() - 730
    return sum(1 for d in change_dates if d.toordinal() >= cutoff)


def ratio_pct(numerator: float | None, denominator: float | None) -> float | None:
    """related_party / revenue, contingent liabilities / networth, ..."""
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator * 100
