"""Pure analytics: XIRR and window returns. Golden-tested."""

from datetime import date
from decimal import Decimal


def xirr(cashflows: list[tuple[date, Decimal]], tol: float = 1e-8) -> float | None:
    """Annualised internal rate of return for dated cashflows (negative = out).

    Bisection on the NPV sign change over (-0.9999, 10.0). Boring, robust,
    inspectable — no Newton overshoot pathologies. Returns None when there is
    no sign change (all flows one-signed) or fewer than two flows.
    """
    if len(cashflows) < 2:
        return None
    flows = sorted(cashflows)
    t0 = flows[0][0]

    def npv(rate: float) -> float:
        return sum(
            float(amount) / (1 + rate) ** ((d - t0).days / 365.0) for d, amount in flows
        )

    lo, hi = -0.9999, 10.0
    npv_lo, npv_hi = npv(lo), npv(hi)
    if npv_lo * npv_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        v = npv(mid)
        if abs(v) < tol:
            return mid
        if npv_lo * v < 0:
            hi = mid
        else:
            lo, npv_lo = mid, v
    return (lo + hi) / 2


def window_return_pct(start_price: Decimal, end_price: Decimal) -> Decimal:
    """Simple holding-window return, percent."""
    return ((end_price / start_price) - 1) * 100
