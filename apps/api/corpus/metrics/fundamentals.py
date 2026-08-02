"""fin.* metrics — pure functions over fundamentals_period line items.

Inputs are plain series, newest last:
  annual:    {"revenue": [(fy_end, value), ...], ...}   FY periods
  quarterly: {"revenue": [(q_end, value), ...], ...}    Q periods
Values in ₹ crore (unit INR_CR). None whenever the series is short — never a
partial CAGR, never an imputed quarter.
"""

import statistics
from datetime import date

Series = list[tuple[date, float]]


def _values(s: Series | None, n: int | None = None) -> list[float] | None:
    if s is None:
        return None
    vals = [v for _, v in s]
    if n is not None:
        if len(vals) < n:
            return None
        vals = vals[-n:]
    return vals


def cagr(annual: Series | None, years: int) -> float | None:
    """CAGR over `years` using FY endpoints; needs years+1 observations."""
    vals = _values(annual, years + 1)
    if vals is None or vals[0] <= 0 or vals[-1] <= 0:
        return None
    return ((vals[-1] / vals[0]) ** (1 / years) - 1) * 100


def ttm_sum(quarterly: Series | None) -> float | None:
    vals = _values(quarterly, 4)
    return None if vals is None else sum(vals)


def ebitda_margin_ttm(revenue_q: Series | None, ebitda_q: Series | None) -> float | None:
    rev, ebd = ttm_sum(revenue_q), ttm_sum(ebitda_q)
    if rev is None or ebd is None or rev == 0:
        return None
    return ebd / rev * 100


def _ols_slope(vals: list[float]) -> float:
    n = len(vals)
    xbar = (n - 1) / 2
    ybar = sum(vals) / n
    num = sum((i - xbar) * (y - ybar) for i, y in enumerate(vals))
    den = sum((i - xbar) ** 2 for i in range(n))
    return num / den


def margin_trend_4q(revenue_q: Series | None, ebitda_q: Series | None) -> float | None:
    """OLS slope of quarterly EBITDA margin, percentage points per quarter."""
    rev, ebd = _values(revenue_q, 4), _values(ebitda_q, 4)
    if rev is None or ebd is None or any(r == 0 for r in rev):
        return None
    margins = [e / r * 100 for e, r in zip(ebd, rev, strict=True)]
    return _ols_slope(margins)


def roce(
    ebit_ttm: float | None,
    equity: float | None,
    total_debt: float | None,
    cash: float | None,
) -> float | None:
    if ebit_ttm is None or equity is None or total_debt is None or cash is None:
        return None
    capital = equity + total_debt - cash
    return None if capital <= 0 else ebit_ttm / capital * 100


def roce_median_5y(roce_annual: Series | None) -> float | None:
    vals = _values(roce_annual, 5)
    return None if vals is None else statistics.median(vals)


def roce_stability_5y(roce_annual: Series | None) -> float | None:
    """1 - (stdev/median), clipped to [0, 1]."""
    vals = _values(roce_annual, 5)
    if vals is None:
        return None
    med = statistics.median(vals)
    if med <= 0:
        return 0.0
    stab = 1 - statistics.stdev(vals) / med
    return min(1.0, max(0.0, stab))


def roe_ttm(pat_q: Series | None, equity: float | None) -> float | None:
    pat = ttm_sum(pat_q)
    if pat is None or equity is None or equity <= 0:
        return None
    return pat / equity * 100


def debt_to_equity(total_debt: float | None, equity: float | None) -> float | None:
    if total_debt is None or equity is None or equity <= 0:
        return None
    return total_debt / equity


def debt_to_equity_trend_8q(
    debt_q: Series | None, equity_q: Series | None
) -> float | None:
    d, e = _values(debt_q, 8), _values(equity_q, 8)
    if d is None or e is None or any(v <= 0 for v in e):
        return None
    return _ols_slope([dv / ev for dv, ev in zip(d, e, strict=True)])


def interest_coverage(ebit_ttm: float | None, interest_ttm: float | None) -> float | None:
    if ebit_ttm is None or interest_ttm is None or interest_ttm <= 0:
        return None
    return ebit_ttm / interest_ttm


def ocf_to_ebitda_5y(ocf_annual: Series | None, ebitda_annual: Series | None) -> float | None:
    o, e = _values(ocf_annual, 5), _values(ebitda_annual, 5)
    if o is None or e is None or sum(e) <= 0:
        return None
    return sum(o) / sum(e)


def fcf_yield(
    ocf_ttm: float | None, capex_ttm: float | None, mcap_cr: float | None
) -> float | None:
    if ocf_ttm is None or capex_ttm is None or mcap_cr is None or mcap_cr <= 0:
        return None
    return (ocf_ttm - capex_ttm) / mcap_cr * 100


def reinvestment_rate(
    capex_ttm: float | None, dep_ttm: float | None, ebit_ttm: float | None
) -> float | None:
    if capex_ttm is None or dep_ttm is None or ebit_ttm is None or ebit_ttm <= 0:
        return None
    return (capex_ttm - dep_ttm) / ebit_ttm * 100


def working_capital_days(
    receivables: float | None,
    inventory: float | None,
    payables: float | None,
    revenue_ttm: float | None,
) -> float | None:
    if None in (receivables, inventory, payables, revenue_ttm) or not revenue_ttm:
        return None
    return (receivables + inventory - payables) / revenue_ttm * 365  # type: ignore[operator]


def wc_days_trend_4q(wc_days_q: Series | None) -> float | None:
    vals = _values(wc_days_q, 4)
    return None if vals is None else _ols_slope(vals)


# earn.* helpers — consensus-free variants per docs/06

def surprise_vs_trend(pat_q: Series | None) -> float | None:
    """Last quarter PAT vs the mean of the prior four — the consensus-free
    surprise. Needs 5 quarters."""
    vals = _values(pat_q, 5)
    if vals is None:
        return None
    expected = sum(vals[:4]) / 4
    if expected == 0:
        return None
    return (vals[-1] - expected) / abs(expected) * 100


def surprise_streak(pat_q: Series | None) -> int | None:
    """Consecutive quarters (from latest, backwards) beating the mean of the
    four quarters before each. Needs at least 5 quarters."""
    if pat_q is None or len(pat_q) < 5:
        return None
    vals = [v for _, v in pat_q]
    streak = 0
    for i in range(len(vals) - 1, 3, -1):
        expected = sum(vals[i - 4 : i]) / 4
        if vals[i] > expected:
            streak += 1
        else:
            break
    return streak
