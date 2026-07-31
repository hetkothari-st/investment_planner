"""Scoring: winsorised sector percentiles, coverage caps, conviction."""

from corpus.research.scoring import (
    composite_scores,
    conviction,
    cross_sectional_percentiles,
    load_weights,
    winsorise,
)


def test_weights_sum_and_version():
    cfg = load_weights()
    assert cfg["version"] == "v1"
    for horizon in ("SHORT", "MID", "LONG"):
        assert abs(sum(abs(w) for w in cfg[horizon].values()) - 1.0) < 1e-9


def test_winsorise_clamps_outliers():
    vals = list(range(100))  # 0..99
    w = winsorise([float(v) for v in vals] + [10_000.0])
    assert max(w) <= 99.0


def test_percentiles_ignore_none_and_break_ties_deterministically():
    p = cross_sectional_percentiles({"a": 10.0, "b": 20.0, "c": None, "d": 20.0})
    assert p["a"] < p["b"]
    assert p["b"] == p["d"]  # midrank ties
    assert "c" not in p


def test_composite_negative_weight_inverts():
    # Two names; only val.pe_pctl_5y differs (negative weight: cheap wins).
    metric_values = {
        "val.pe_pctl_5y": {"CHEAP": 10.0, "DEAR": 90.0},
        "earn.revision_3m": {"CHEAP": 1.0, "DEAR": 1.0},
    }
    sectors = {"CHEAP": "IT", "DEAR": "IT"}
    scores = {s.isin: s for s in composite_scores("MID", metric_values, sectors)}
    assert scores["CHEAP"].composite_pctl > scores["DEAR"].composite_pctl


def test_coverage_fraction():
    metric_values = {
        "fin.roce_median_5y": {"A": 20.0},  # weight 0.22
        "gov.pledge_pct": {"A": 1.0},       # weight 0.14
    }
    s = composite_scores("LONG", metric_values, {"A": "IT"})[0]
    assert abs(s.coverage - 0.36) < 1e-9  # (0.22+0.14)/1.00


def test_conviction_caps_on_coverage():
    assert conviction(95, 0.90) == "HIGH"
    assert conviction(95, 0.80) == "MODERATE"  # great score, thin coverage
    assert conviction(95, 0.50) == "LOW"
    assert conviction(80, 0.95) == "MODERATE"
    assert conviction(60, 1.00) == "LOW"
