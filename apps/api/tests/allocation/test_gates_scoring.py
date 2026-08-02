"""Gates and scoring — docs/04 tests: reachability, horizon exclusion,
tax drag, plus hand-checked golden values for the fit functions."""

from decimal import Decimal

import pytest

from corpus.allocation.engine import (
    UserContext,
    failed_gate,
    fits,
    net_expected_return,
    suitability_pct,
)
from corpus.allocation.schemas import Knowledge
from corpus.allocation.vehicles import load_vehicles

D = Decimal
CFG = load_vehicles()
INFLATION = D("5.0")  # assumptions.v1


CORPUS_10L = D("1000000")
BUY_MORE_FRAC = D("0.45")
FULL_EQUITY = D("1")


def ctx(
    horizon=96,
    corpus=CORPUS_10L,
    dd_frac=BUY_MORE_FRAC,
    knowledge=Knowledge.HIGH,
    max_lock=None,
    max_equity=FULL_EQUITY,
) -> UserContext:
    return UserContext(
        horizon_months=horizon,
        corpus=corpus,
        max_tolerable_dd_inr=(dd_frac * corpus).quantize(D("0.01")),
        max_equity_fraction=max_equity,
        self_rated_knowledge=knowledge,
        max_lock_in_months=max_lock,
    )


# --- reachability: no dead entries (docs/04) -------------------------------


def test_every_enabled_vehicle_reachable_by_some_profile():
    """A permissive-but-valid profile (BUY_MORE temperament, 120-month
    horizon, HIGH knowledge, no lock-in constraint) must pass every enabled
    vehicle. If a config edit makes a vehicle unreachable, this fails."""
    u = ctx(horizon=120)
    for v in CFG.vehicles:
        if not v.enabled:
            continue
        assert failed_gate(v, u, CFG) is None, (v.id, failed_gate(v, u, CFG))


def test_fno_always_gated_regardless_of_profile():
    fno = CFG.by_id("derivatives.fno")
    gate, _ = failed_gate(fno, ctx(horizon=120), CFG)
    assert gate == "module_disabled"


# --- horizon: the acceptance rule ------------------------------------------


def test_six_month_horizon_gates_out_every_equity_vehicle():
    u = ctx(horizon=6)
    for v in CFG.vehicles:
        if v.id.startswith("equity"):
            gate, _ = failed_gate(v, u, CFG)
            assert gate == "horizon", v.id


def test_lock_in_gate_only_when_constraint_stated():
    sgb = CFG.by_id("commodity.sgb")
    assert failed_gate(sgb, ctx(max_lock=None), CFG) is None
    gate, _ = failed_gate(sgb, ctx(max_lock=12), CFG)
    assert gate == "lock_in"


def test_drawdown_gate_at_max_weight():
    """SELL_EVERYTHING (10% tolerance): dd ceiling is 10/0.40 = 25%.
    Balanced advantage (22%) squeaks through; gold (30%) does not."""
    u = ctx(horizon=96, dd_frac=D("0.10"), knowledge=Knowledge.LOW)
    assert failed_gate(CFG.by_id("hybrid.balanced_advantage"), u, CFG) is None
    gate, _ = failed_gate(CFG.by_id("commodity.gold_etf"), u, CFG)
    assert gate == "drawdown"


def test_knowledge_gate():
    direct = CFG.by_id("equity.direct_midsmall")
    gate, _ = failed_gate(direct, ctx(horizon=120, knowledge=Knowledge.LOW), CFG)
    assert gate == "knowledge"
    assert failed_gate(direct, ctx(horizon=120, knowledge=Knowledge.HIGH), CFG) is None


# --- net expected return: hand-checked golden values -----------------------


def test_ner_index_largecap_long_horizon():
    # gross 7.0 + 5.0 = 12.0; after cost 12.0 - 0.05 - 0.20 = 11.75;
    # LTCG 12.5%: 11.75 * 0.875 = 10.28125 -> 10.28
    v = CFG.by_id("equity.index_largecap")
    assert net_expected_return(v, 96, INFLATION) == D("10.28")


def test_ner_fd_short_horizon():
    # gross 1.5 + 5.0 = 6.5; after cost 6.5 - 0.1 = 6.4; slab 30%:
    # 6.4 * 0.7 = 4.48
    v = CFG.by_id("liquid.fd")
    assert net_expected_return(v, 6, INFLATION) == D("4.48")


def test_tax_drag_11_vs_13_months():
    """docs/04: same vehicle, 11 vs 13 months — the score must drop for the
    shorter horizon because STCG applies below the 12-month threshold."""
    v = CFG.by_id("hybrid.balanced_advantage")
    ner_11 = net_expected_return(v, 11, INFLATION)
    ner_13 = net_expected_return(v, 13, INFLATION)
    # after cost 9.0 - 0.8 = 8.2; STCG 20% -> 6.56; LTCG 12.5% -> 7.175 -> 7.18
    assert ner_11 == D("6.56")
    assert ner_13 == D("7.18")
    assert ner_11 < ner_13

    s11 = suitability_pct(fits(v, ctx(horizon=11), CFG, INFLATION), CFG)
    s13 = suitability_pct(fits(v, ctx(horizon=13), CFG, INFLATION), CFG)
    assert s11 < s13


# --- fit functions: hand-checked -------------------------------------------


def test_fit_horizon_symmetry():
    u6 = ctx(horizon=6)
    overnight = CFG.by_id("liquid.overnight_fund")  # natural 6
    savings = CFG.by_id("liquid.savings")  # natural 3
    assert fits(overnight, u6, CFG, INFLATION)["fit_horizon"] == D("1.0000")
    assert fits(savings, u6, CFG, INFLATION)["fit_horizon"] == D("0.5000")
    # a savings account is a poor home for 10-year money
    u120 = ctx(horizon=120)
    assert fits(savings, u120, CFG, INFLATION)["fit_horizon"] == D("0.0250")


def test_fit_liquidity_counts_lock_in():
    sgb = CFG.by_id("commodity.sgb")  # 5 days + 60-month lock -> illiquid
    assert fits(sgb, ctx(), CFG, INFLATION)["fit_liquidity"] == D("0")
    savings = CFG.by_id("liquid.savings")
    assert fits(savings, ctx(), CFG, INFLATION)["fit_liquidity"] == D("1")


def test_fit_drawdown_hand_checked():
    # HOLD tolerance 32% of 10L = 3.2L; largecap worst at max weight:
    # 55% * 0.40 * 10L = 2.2L; fit = 1 - 2.2/3.2 = 0.3125
    v = CFG.by_id("equity.index_largecap")
    u = ctx(dd_frac=D("0.32"))
    assert fits(v, u, CFG, INFLATION)["fit_drawdown"] == D("0.3125")


def test_suitability_deterministic():
    v = CFG.by_id("equity.index_largecap")
    u = ctx()
    a = suitability_pct(fits(v, u, CFG, INFLATION), CFG)
    b = suitability_pct(fits(v, u, CFG, INFLATION), CFG)
    assert a == b
    assert D(0) <= a <= D(100)


@pytest.mark.parametrize("vehicle_id", [v.id for v in CFG.vehicles if v.enabled])
def test_all_components_in_unit_range(vehicle_id):
    comps = fits(CFG.by_id(vehicle_id), ctx(), CFG, INFLATION)
    for name, value in comps.items():
        assert D(0) <= value <= D(1), (vehicle_id, name, value)
