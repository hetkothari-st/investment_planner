"""Price-series metrics: price.*, tech.*, mom.*, risk.*, vol.*, liq.*.

Pure functions over adjusted daily bars, newest last. Every function returns
None when history is insufficient — never a partial answer. Statistical
metrics use float internally; the persistence layer quantizes per registry
precision.
"""

import math
from typing import NamedTuple


class Bar(NamedTuple):
    close: float
    volume: int | None = None
    high: float | None = None
    low: float | None = None


# Trading-day windows
D_1M, D_3M, D_6M, D_1Y, D_3Y = 21, 63, 126, 252, 756


def _closes(bars: list[Bar]) -> list[float]:
    return [b.close for b in bars]


def last_close(bars: list[Bar]) -> float | None:
    return bars[-1].close if bars else None


def high_52w(bars: list[Bar]) -> float | None:
    if len(bars) < D_1Y:
        return None
    return max(_closes(bars[-D_1Y:]))


def low_52w(bars: list[Bar]) -> float | None:
    if len(bars) < D_1Y:
        return None
    return min(_closes(bars[-D_1Y:]))


def dist_from_52w_high(bars: list[Bar]) -> float | None:
    hi = high_52w(bars)
    return None if hi is None else (bars[-1].close / hi - 1) * 100


def dist_from_52w_low(bars: list[Bar]) -> float | None:
    lo = low_52w(bars)
    return None if lo is None else (bars[-1].close / lo - 1) * 100


def ret_window(bars: list[Bar], days: int, skip: int = 0) -> float | None:
    """Return over the `days` window ending `skip` days before the last bar."""
    need = days + skip + 1
    if len(bars) < need:
        return None
    end = bars[-1 - skip].close
    start = bars[-1 - skip - days].close
    return (end / start - 1) * 100


def relative_strength(
    bars: list[Bar], benchmark: list[Bar], days: int
) -> float | None:
    r_stock = ret_window(bars, days)
    r_bench = ret_window(benchmark, days)
    if r_stock is None or r_bench is None:
        return None
    return r_stock - r_bench


def consistency_6m(bars: list[Bar], benchmark: list[Bar]) -> float | None:
    """Fraction of the last 26 weeks with positive weekly relative strength."""
    weeks = 26
    need = weeks * 5 + 1
    if len(bars) < need or len(benchmark) < need:
        return None
    wins = 0
    for w in range(weeks):
        s1, s0 = bars[-1 - w * 5].close, bars[-1 - (w + 1) * 5].close
        b1, b0 = benchmark[-1 - w * 5].close, benchmark[-1 - (w + 1) * 5].close
        if s1 / s0 > b1 / b0:
            wins += 1
    return wins / weeks


def _log_returns(closes: list[float]) -> list[float]:
    return [math.log(b / a) for a, b in zip(closes, closes[1:], strict=False)]


def vol_ann_1y(bars: list[Bar]) -> float | None:
    if len(bars) < D_1Y:
        return None
    rets = _log_returns(_closes(bars[-D_1Y:]))
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252) * 100


def beta_1y(bars: list[Bar], benchmark: list[Bar]) -> float | None:
    if len(bars) < D_1Y or len(benchmark) < D_1Y:
        return None
    rs = _log_returns(_closes(bars[-D_1Y:]))
    rb = _log_returns(_closes(benchmark[-D_1Y:]))
    mean_s, mean_b = sum(rs) / len(rs), sum(rb) / len(rb)
    cov = sum((a - mean_s) * (b - mean_b) for a, b in zip(rs, rb, strict=True))
    var_b = sum((b - mean_b) ** 2 for b in rb)
    return None if var_b == 0 else cov / var_b


def max_dd_3y(bars: list[Bar]) -> float | None:
    if len(bars) < D_3Y:
        return None
    peak, worst = float("-inf"), 0.0
    for c in _closes(bars[-D_3Y:]):
        peak = max(peak, c)
        worst = min(worst, (c / peak - 1) * 100)
    return worst


def downside_dev_1y(bars: list[Bar]) -> float | None:
    if len(bars) < D_1Y:
        return None
    rets = _log_returns(_closes(bars[-D_1Y:]))
    downs = [r for r in rets if r < 0]
    if not downs:
        return 0.0
    return math.sqrt(sum(r * r for r in downs) / len(rets)) * math.sqrt(252) * 100


def ulcer_index_1y(bars: list[Bar]) -> float | None:
    if len(bars) < D_1Y:
        return None
    peak, sq_sum = float("-inf"), 0.0
    closes = _closes(bars[-D_1Y:])
    for c in closes:
        peak = max(peak, c)
        dd = (c / peak - 1) * 100
        sq_sum += dd * dd
    return math.sqrt(sq_sum / len(closes))


def volume_multiple(bars: list[Bar]) -> float | None:
    if len(bars) < 21:
        return None
    window = [b.volume for b in bars[-21:-1]]
    latest = bars[-1].volume
    if latest is None or any(v is None for v in window):
        return None
    adv = sum(window) / 20  # type: ignore[arg-type]
    return None if adv == 0 else latest / adv


def obv_slope_3m(bars: list[Bar]) -> float | None:
    """OLS slope of on-balance volume over 3 months, normalised by mean daily
    volume — a unitless score comparable across symbols."""
    if len(bars) < D_3M + 1:
        return None
    window = bars[-(D_3M + 1):]
    if any(b.volume is None for b in window):
        return None
    obv, series = 0.0, []
    for prev, cur in zip(window, window[1:], strict=False):
        sign = 1 if cur.close > prev.close else -1 if cur.close < prev.close else 0
        obv += sign * (cur.volume or 0)
        series.append(obv)
    mean_vol = sum(b.volume or 0 for b in window[1:]) / len(series)
    if mean_vol == 0:
        return None
    n = len(series)
    xbar = (n - 1) / 2
    ybar = sum(series) / n
    num = sum((i - xbar) * (y - ybar) for i, y in enumerate(series))
    den = sum((i - xbar) ** 2 for i in range(n))
    return (num / den) / mean_vol


def adv_20d_inr_cr(bars: list[Bar]) -> float | None:
    """Mean of close x volume over the last 20 bars, in ₹ crore."""
    if len(bars) < 20:
        return None
    window = bars[-20:]
    if any(b.volume is None for b in window):
        return None
    turnover = sum(b.close * (b.volume or 0) for b in window) / 20
    return turnover / 1e7


def spread_bps_est(bars: list[Bar]) -> float | None:
    """Daily-range proxy until intraday data exists: a quarter of the median
    (high-low)/close over 20 days, in basis points. Documented approximation."""
    if len(bars) < 20:
        return None
    window = bars[-20:]
    if any(b.high is None or b.low is None for b in window):
        return None
    ranges = sorted((b.high - b.low) / b.close for b in window)  # type: ignore[operator]
    median = ranges[len(ranges) // 2]
    return median / 4 * 10_000


def slippage_est_pct(
    order_value_inr: float, adv_inr: float, spread_bps: float
) -> float:
    """docs/05: max(0.05%, 0.5 x (spread_bps/10000) x sqrt(order_value/adv))."""
    if adv_inr <= 0:
        return 0.05
    est = 0.5 * (spread_bps / 10_000) * math.sqrt(order_value_inr / adv_inr) * 100
    return max(0.05, est)


def impact_cost_1l(bars: list[Bar]) -> float | None:
    adv_cr = adv_20d_inr_cr(bars)
    spread = spread_bps_est(bars)
    if adv_cr is None or spread is None or adv_cr == 0:
        return None
    return slippage_est_pct(100_000, adv_cr * 1e7, spread)


def days_to_exit(position_value_inr: float, adv_inr: float) -> float | None:
    """position_value / (0.10 x ADV): days to exit at a tenth of daily volume."""
    if adv_inr <= 0:
        return None
    return position_value_inr / (0.10 * adv_inr)
