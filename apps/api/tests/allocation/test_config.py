"""The vehicle taxonomy is versioned config, not code. Sanity-check it."""

from decimal import Decimal

from corpus.allocation.vehicles import load_vehicles

TAXONOMY = {
    "liquid.savings", "liquid.overnight_fund", "liquid.fd",
    "debt.short_duration", "debt.corporate_bond", "debt.gilt",
    "hybrid.balanced_advantage", "hybrid.multi_asset",
    "equity.index_largecap", "equity.index_midcap", "equity.flexicap_active",
    "equity.direct_largecap", "equity.direct_midsmall",
    "derivatives.fno", "commodity.gold_etf", "commodity.sgb",
    "reit", "invit", "intl.us_index",
}


def test_taxonomy_complete():
    cfg = load_vehicles()
    assert {v.id for v in cfg.vehicles} == TAXONOMY
    assert cfg.version == "v1"


def test_only_fno_disabled():
    cfg = load_vehicles()
    disabled = {v.id for v in cfg.vehicles if not v.enabled}
    assert disabled == {"derivatives.fno"}
    fno = cfg.by_id("derivatives.fno")
    assert fno.disabled_reason  # the gate must be able to name itself


def test_declared_characteristics_sane():
    cfg = load_vehicles()
    for v in cfg.vehicles:
        assert v.volatility_annual_pct >= 0
        assert 0 <= v.max_historical_dd_pct <= 100
        assert v.liquidity_days >= 0
        assert v.lock_in_months >= 0
        assert v.natural_horizon_months >= 1
        assert Decimal(0) <= v.tax.short_term.rate <= Decimal("0.5")
        assert Decimal(0) <= v.tax.long_term.rate <= Decimal("0.5")
        assert v.effort in ("LOW", "MEDIUM", "HIGH")
        assert v.knowledge_required in ("LOW", "MEDIUM", "HIGH")


def test_weights_sum_to_one():
    s = load_vehicles().scoring
    assert s.w_horizon + s.w_drawdown + s.w_liquidity + s.w_return + s.w_effort == 1
