"""Empirical bands: quantiles, shrinkage, fallback honesty."""

from corpus.research.bands import (
    MIN_ANALOGUES,
    Band,
    quantile,
    rolling_forward_returns,
    scenario_band,
)


def test_rolling_forward_returns():
    import pytest

    closes = [100.0, 110.0, 121.0]
    assert rolling_forward_returns(closes, 1) == pytest.approx([10.0, 10.0])
    assert rolling_forward_returns(closes, 5) == []


def test_quantile_interpolation():
    vals = [0.0, 10.0, 20.0, 30.0, 40.0]
    assert quantile(vals, 0.5) == 20.0
    assert quantile(vals, 0.20) == 8.0  # pos 0.8 between 0 and 10
    assert quantile(vals, 1.0) == 40.0


def test_band_ordering_always_holds():
    returns = [float(v) for v in range(-20, 30)]  # -20..29
    band = scenario_band(returns, [])
    assert band is not None
    assert band.bear_pct < band.base_pct < band.bull_pct
    assert band.n_analogues == 50
    assert band.conditioned is False


def test_degenerate_distribution_yields_no_band():
    assert scenario_band([5.0] * 100, []) is None  # constant: no honest band


def test_shrinkage_pulls_toward_sector():
    own = [10.0] * 30 + [12.0] * 30  # tight, high
    sector = [-30.0, -10.0, 0.0, 10.0, 30.0] * 20  # wide
    shrunk = scenario_band(own, sector)
    pure = scenario_band(own, [])
    assert shrunk is not None and pure is not None
    assert shrunk.bear_pct < pure.bear_pct  # sector's fat left tail shows up


def test_conditioning_needs_min_analogues():
    own = [float(v) for v in range(-20, 30)]
    few = [1.0, 2.0, 3.0]
    band = scenario_band(own, [], conditioned_returns=few)
    assert band is not None and band.conditioned is False  # fell back
    many = [float(v) for v in range(MIN_ANALOGUES + 5)]
    band2 = scenario_band(own, [], conditioned_returns=many)
    assert band2 is not None and band2.conditioned is True
    assert isinstance(band2, Band)
