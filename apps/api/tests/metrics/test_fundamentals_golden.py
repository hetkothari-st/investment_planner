"""Hand-checked golden values for fin.*, earn.*, gov.*, val.* helpers."""

from datetime import date

from corpus.metrics.fundamentals import (
    cagr,
    debt_to_equity,
    debt_to_equity_trend_8q,
    ebitda_margin_ttm,
    fcf_yield,
    interest_coverage,
    margin_trend_4q,
    ocf_to_ebitda_5y,
    reinvestment_rate,
    roce,
    roce_median_5y,
    roce_stability_5y,
    surprise_streak,
    surprise_vs_trend,
    wc_days_trend_4q,
    working_capital_days,
)
from corpus.metrics.governance import auditor_changes_24m, latest, ratio_pct, trend_4q
from corpus.metrics.valuation import (
    earnings_yield_spread,
    pe_ttm,
    percentile_of_last,
    ratio_history,
)


def fy(vals: list[float]) -> list[tuple[date, float]]:
    return [(date(2020 + i, 3, 31), v) for i, v in enumerate(vals)]


def q(vals: list[float]) -> list[tuple[date, float]]:
    return [(date(2024, 3, 31), v) for v in vals]  # dates unused by the maths


def test_cagr_doubling_in_three_years():
    # 100 -> 200 over 3y: 2^(1/3)-1 = 25.9921%
    assert round(cagr(fy([100, 120, 160, 200]), 3), 4) == 25.9921
    assert cagr(fy([100, 200]), 3) is None  # needs 4 points
    assert cagr(fy([-5, 100, 100, 100]), 3) is None  # negative base


def test_margins():
    rev, ebd = q([100, 110, 120, 130]), q([20, 22, 30, 32.5])
    # TTM: 104.5/460 = 22.7174%
    assert round(ebitda_margin_ttm(rev, ebd), 4) == 22.7174
    # margins 20, 20, 25, 25 -> OLS slope over x=0..3 is 2.0 pp/q
    assert margin_trend_4q(rev, ebd) == 2.0


def test_roce_and_stability():
    # EBIT 45 on capital (200 + 100 - 45) = 255 -> 17.6471%
    assert round(roce(45, 200, 100, 45), 4) == 17.6471
    series = fy([18, 20, 22, 20, 19])
    assert roce_median_5y(series) == 20
    stab = roce_stability_5y(series)
    assert 0.9 < stab < 1  # stdev ~1.48 on median 20 -> ~0.926
    assert roce_stability_5y(fy([1, 40, 2, 38, 3])) == 0.0  # clipped


def test_leverage_and_coverage():
    assert debt_to_equity(150, 300) == 0.5
    assert debt_to_equity(150, -10) is None
    # D/E rising 0.5 -> 0.85 in equal steps of 0.05 over 8q: slope 0.05
    debt = q([50, 55, 60, 65, 70, 75, 80, 85])
    equity = q([100] * 8)
    assert round(debt_to_equity_trend_8q(debt, equity), 6) == 0.05
    assert interest_coverage(45, 9) == 5.0
    assert interest_coverage(45, 0) is None


def test_cash_conversion_and_fcf():
    assert ocf_to_ebitda_5y(fy([80, 85, 90, 95, 100]), fy([100] * 5)) == 0.9
    # (OCF 90 - capex 40) / mcap 1000 = 5%
    assert fcf_yield(90, 40, 1000) == 5.0
    assert reinvestment_rate(40, 15, 50) == 50.0


def test_working_capital():
    # (60 + 80 - 50) / 365 revenue x 365 = 90 days
    assert working_capital_days(60, 80, 50, 365) == 90.0
    assert wc_days_trend_4q(q([80, 84, 88, 92])) == 4.0


def test_surprise_vs_trend_and_streak():
    # prior 4 mean = 100; latest 110 -> +10%
    pat = q([100, 100, 100, 100, 110])
    assert surprise_vs_trend(pat) == 10.0
    # rising every quarter beats each trailing mean -> streak counts to base
    rising = q([100, 104, 108, 112, 116, 120])
    assert surprise_streak(rising) == 2  # only indices 5 and 4 have 4 priors
    flat = q([100] * 6)
    assert surprise_streak(flat) == 0


def test_governance():
    sh = [(date(2025, 3, 31), 8.0), (date(2025, 6, 30), 10.0),
          (date(2025, 9, 30), 12.0), (date(2025, 12, 31), 14.0)]
    assert latest(sh) == 14.0
    assert trend_4q(sh) == 2.0  # +2pp per quarter
    assert auditor_changes_24m([date(2025, 1, 1), date(2020, 1, 1)], date(2026, 7, 1)) == 1
    assert ratio_pct(12, 400) == 3.0
    assert ratio_pct(12, 0) is None


def test_valuation():
    assert pe_ttm(300, 15) == 20.0
    assert pe_ttm(300, -2) is None
    # history 1..99 + current 50 -> 49 below, 1 equal (itself) -> 49.5/100
    history = [float(v) for v in range(1, 100)] + [50.0]
    assert percentile_of_last(history, min_n=50) == 50.0
    assert percentile_of_last(history, min_n=200) is None
    assert ratio_history([100, 200], [10, 0]) == [10.0]  # non-positive day dropped
    # earnings yield 5% - gsec 7.2% = -2.2
    assert round(earnings_yield_spread(20, 7.2), 4) == -2.2
