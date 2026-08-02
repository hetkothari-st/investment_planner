"""Hand-checked golden values for price-series metrics. Fixtures are tiny and
deliberately checkable on paper."""

import math

from corpus.metrics.series import (
    Bar,
    adv_20d_inr_cr,
    beta_1y,
    consistency_6m,
    days_to_exit,
    dist_from_52w_high,
    dist_from_52w_low,
    high_52w,
    low_52w,
    max_dd_3y,
    obv_slope_3m,
    relative_strength,
    ret_window,
    slippage_est_pct,
    spread_bps_est,
    ulcer_index_1y,
    vol_ann_1y,
    volume_multiple,
)


def flat_bars(n: int, close: float = 100.0, volume: int = 1000) -> list[Bar]:
    return [Bar(close=close, volume=volume, high=close + 1, low=close - 1)] * n


def test_insufficient_history_is_none_not_partial():
    short = flat_bars(50)
    assert high_52w(short) is None
    assert vol_ann_1y(short) is None
    assert max_dd_3y(short) is None
    assert ret_window(short, 63) is None
    assert consistency_6m(short, short) is None


def test_52w_and_distances():
    bars = flat_bars(252)
    bars[100] = Bar(close=150.0, volume=1000)  # the year's high
    bars[200] = Bar(close=80.0, volume=1000)   # the year's low
    assert high_52w(bars) == 150.0
    assert low_52w(bars) == 80.0
    # last close 100: (100/150 - 1) = -33.33%, (100/80 - 1) = +25%
    assert round(dist_from_52w_high(bars), 4) == -33.3333
    assert dist_from_52w_low(bars) == 25.0


def test_returns_and_skip_month():
    # closes 100 -> 110 over last 21 bars; before that flat at 100
    bars = flat_bars(300)
    bars = bars[:-1] + [Bar(close=110.0, volume=1000)]
    assert round(ret_window(bars, 21), 4) == 10.0
    # 12m-ex-1m skips the final month: flat 100 -> 100 = 0
    assert ret_window(bars, 252, skip=21) == 0.0


def test_relative_strength():
    stock = flat_bars(64)[:-1] + [Bar(close=112.0, volume=1)]
    bench = flat_bars(64)[:-1] + [Bar(close=105.0, volume=1)]
    assert round(relative_strength(stock, bench, 63), 4) == 7.0


def test_vol_ann_alternating_sequence():
    # closes alternate 100, 101: daily log returns alternate +r, -r
    bars = [Bar(close=100.0 if i % 2 == 0 else 101.0, volume=1) for i in range(253)]
    v = vol_ann_1y(bars)
    r = math.log(101 / 100)
    # sample stdev of alternating +-r with even count ~ r (tiny mean correction)
    assert abs(v - r * math.sqrt(252) * 100) < 0.05


def test_beta_of_benchmark_with_itself_is_one():
    bars = [Bar(close=100.0 + (i % 7), volume=1) for i in range(260)]
    assert round(beta_1y(bars, bars), 6) == 1.0


def test_max_dd_3y():
    bars = flat_bars(756)
    bars[300] = Bar(close=200.0, volume=1)
    bars[400] = Bar(close=120.0, volume=1)
    # peak 200; the flat 100s after the spike are the true trough: -50%
    assert max_dd_3y(bars) == -50.0


def test_ulcer_flat_series_is_zero():
    assert ulcer_index_1y(flat_bars(252)) == 0.0


def test_volume_multiple():
    bars = flat_bars(21)[:-1] + [Bar(close=100.0, volume=5000)]
    # prior 20 bars at 1000 -> ADV 1000; latest 5000 -> 5x
    assert volume_multiple(bars) == 5.0


def test_obv_slope_sign():
    up = [Bar(close=100.0 + i, volume=1000) for i in range(70)]
    down = [Bar(close=200.0 - i, volume=1000) for i in range(70)]
    assert obv_slope_3m(up) > 0
    assert obv_slope_3m(down) < 0


def test_adv_and_exit_days():
    # 20 bars, close 100 x volume 1_000_000 = ₹10 cr/day
    bars = flat_bars(20, close=100.0, volume=1_000_000)
    assert adv_20d_inr_cr(bars) == 10.0
    # ₹5L position at 10% participation of ₹10cr ADV -> 0.005 days
    assert days_to_exit(500_000, 10e7) == 0.05


def test_spread_proxy_and_slippage_floor():
    bars = flat_bars(20, close=100.0)  # high-low = 2 -> range 2% -> proxy 50bps
    assert spread_bps_est(bars) == 50.0
    # small order: floor binds
    assert slippage_est_pct(10_000, 10e7, 50.0) == 0.05
    # big order: 0.5 x 0.005 x sqrt(5e7/10e7) = 0.001767... -> 0.1768%
    assert round(slippage_est_pct(5e7, 10e7, 50.0), 4) == 0.1768
