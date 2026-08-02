"""Bucket-filling: the M7 acceptance tests plus three archetype snapshots.

Regenerate snapshots after an intentional engine/config change with:
    CORPUS_REGEN_SNAPSHOTS=1 uv run pytest tests/allocation/test_engine.py
then hand-check the diff before committing. A snapshot change without an
intentional cause is a regression, not noise.
"""

import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from corpus.allocation.engine import build_allocation
from corpus.allocation.schemas import AllocationPreferences, Knowledge
from corpus.allocation.vehicles import load_vehicles
from corpus.planner.engine import compute_plan
from corpus.planner.schemas import HorizonBucket, PlanInput, PlanResult
from corpus.planner.temperament import TemperamentChoice

D = Decimal
CFG = load_vehicles()
INFLATION = D("5.0")
SNAP_DIR = Path(__file__).parent / "snapshots"
AS_OF = date(2026, 7, 31)


MAX_EQUITY_DEFAULT = D("0.71")


def make_plan(
    buckets: dict[HorizonBucket, Decimal],
    monthly: Decimal,
    max_equity: Decimal = MAX_EQUITY_DEFAULT,
) -> PlanResult:
    full = {b: buckets.get(b, D(0)) for b in HorizonBucket}
    return PlanResult(
        gates=[],
        investable_monthly=monthly,
        investable_lumpsum=sum(full.values(), D(0)),
        buffer_target=D(0),
        buffer_current=D(0),
        buffer_eta_months=None,
        blocking_reasons=[],
        spending_recommendations=[],
        max_equity_fraction=max_equity,
        horizon_buckets=full,
        assumptions_version="v1",
        sensitivity=[],
    )


ARCHETYPES = {
    # cautious first-time investor: SELL_SOME tolerance gates all direct
    # equity; LOW knowledge gates HIGH-knowledge vehicles
    "cautious": dict(
        plan=make_plan({HorizonBucket.EQUITY_60_PLUS: D("300000")}, D("40000")),
        prefs=AllocationPreferences(self_rated_knowledge=Knowledge.LOW),
        temperament=TemperamentChoice.SELL_SOME,
        corpus=D("900000"),
    ),
    # seasoned holder: HOLD temperament, HIGH knowledge, three buckets
    "seasoned": dict(
        plan=make_plan(
            {
                HorizonBucket.DEBT_12_36: D("1000000"),
                HorizonBucket.HYBRID_36_60: D("800000"),
                HorizonBucket.EQUITY_60_PLUS: D("2600000"),
            },
            D("150000"),
        ),
        prefs=AllocationPreferences(self_rated_knowledge=Knowledge.HIGH),
        temperament=TemperamentChoice.HOLD,
        corpus=D("7000000"),
    ),
    # aggressive accumulator: BUY_MORE, MEDIUM knowledge -> index floor binds
    "aggressive": dict(
        plan=make_plan({HorizonBucket.EQUITY_60_PLUS: D("1500000")}, D("100000")),
        prefs=AllocationPreferences(self_rated_knowledge=Knowledge.MEDIUM),
        temperament=TemperamentChoice.BUY_MORE,
        corpus=D("2000000"),
    ),
}


def build(name: str):
    a = ARCHETYPES[name]
    return build_allocation(
        plan=a["plan"], prefs=a["prefs"], temperament=a["temperament"],
        corpus=a["corpus"], cfg=CFG, inflation_pct=INFLATION,
    )


# --- the acceptance rule: 6-month money never touches equity ---------------


def test_six_month_profile_receives_no_equity_line_end_to_end():
    """Through the real planner: buffer funded, one 6-month goal consuming
    the entire investable lumpsum. Every line must be non-equity."""
    inp = PlanInput(
        profile=dict(
            monthly_inflow="200000", fixed_outflow="60000",
            variable_outflow="40000", liquid_balance="1000000",
            temperament_choice="BUY_MORE",  # even max risk appetite
        ),
        debts=[],
        goals=[
            dict(label="Wedding", target_amount="400000",
                 target_date="2027-01-31", priority="MUST"),
        ],
        as_of=AS_OF,
    )
    plan = compute_plan(inp)
    assert not plan.blocking_reasons
    assert plan.horizon_buckets[HorizonBucket.LIQUID_0_12] == D("400000")
    assert plan.horizon_buckets[HorizonBucket.EQUITY_60_PLUS] == D(0)

    allocation = build_allocation(
        plan=plan,
        prefs=AllocationPreferences(self_rated_knowledge=Knowledge.HIGH),
        temperament=TemperamentChoice.BUY_MORE,
        corpus=D("1000000"),
        cfg=CFG,
        inflation_pct=INFLATION,
    )
    assert allocation.lines  # the money went somewhere
    for line in allocation.lines:
        assert not line.vehicle_id.startswith("equity"), line
    # and the ranked view says why equity is absent
    equity_gates = {
        g.vehicle_id: g.gate
        for g in allocation.gated_out
        if g.vehicle_id.startswith("equity")
    }
    assert equity_gates and all(g == "horizon" for g in equity_gates.values())


# --- conservation + constraint invariants for every archetype --------------


@pytest.mark.parametrize("name", list(ARCHETYPES))
def test_totals_conserve_exactly(name):
    a = ARCHETYPES[name]
    allocation = build(name)
    total_lumpsum = sum((line.lumpsum_inr for line in allocation.lines), D(0))
    total_monthly = sum((line.monthly_inr for line in allocation.lines), D(0))
    assert total_lumpsum == a["plan"].investable_lumpsum
    assert total_monthly == a["plan"].investable_monthly


@pytest.mark.parametrize("name", list(ARCHETYPES))
def test_single_vehicle_ceiling(name):
    a = ARCHETYPES[name]
    allocation = build(name)
    cap_frac = CFG.construction.max_vehicle_weight
    step = CFG.construction.sip_round_inr
    relaxed = " ".join(allocation.diversification_notes)
    per_bucket: dict[tuple, Decimal] = {}
    for line in allocation.lines:
        per_bucket[(line.bucket, line.vehicle_id)] = line.lumpsum_inr
    for (bucket, vid), amt in per_bucket.items():
        bucket_total = a["plan"].horizon_buckets[bucket] or a["plan"].investable_monthly
        if vid in relaxed or CFG.by_id(vid).label in relaxed:
            continue  # a named, explained relaxation
        assert amt <= bucket_total * cap_frac + step, (bucket, vid, amt)


def test_index_floor_binds_for_non_high_knowledge():
    allocation = build("aggressive")
    equity_lines = [
        line for line in allocation.lines
        if line.bucket == HorizonBucket.EQUITY_60_PLUS
    ]
    bucket_total = sum((line.lumpsum_inr for line in equity_lines), D(0))
    index_total = sum(
        (line.lumpsum_inr for line in equity_lines
         if line.vehicle_id.startswith("equity.index")),
        D(0),
    )
    assert index_total >= bucket_total * CFG.construction.index_floor


def test_seasoned_high_knowledge_never_knowledge_gated():
    """HIGH knowledge opens direct equity's gate. Whether it *wins* is up to
    the effort-weighted score — eligibility and allocation are different
    things, and the snapshot shows funds outscoring direct holdings."""
    allocation = build("seasoned")
    ids = {line.vehicle_id for line in allocation.lines}
    assert any(i.startswith("equity.") for i in ids)
    assert all(g.gate != "knowledge" for g in allocation.gated_out)
    ranked_ids = {r.vehicle_id for r in allocation.ranked_vehicles}
    assert "equity.direct_largecap" in ranked_ids


def test_cautious_temperament_gates_equity_and_says_so():
    allocation = build("cautious")
    ids = {line.vehicle_id for line in allocation.lines}
    assert not any(i.startswith("equity.") for i in ids)
    dd_gated = {g.vehicle_id for g in allocation.gated_out if g.gate == "drawdown"}
    assert "equity.index_largecap" in dd_gated


@pytest.mark.parametrize("name", list(ARCHETYPES))
def test_category_ceilings(name):
    a = ARCHETYPES[name]
    allocation = build(name)
    total = a["plan"].investable_lumpsum
    step = CFG.construction.sip_round_inr
    for prefix, ceiling in (
        ("commodity", CFG.construction.gold_ceiling),
        ("intl", CFG.construction.intl_ceiling),
    ):
        cat = sum(
            (line.lumpsum_inr for line in allocation.lines
             if line.vehicle_id.startswith(prefix)),
            D(0),
        )
        assert cat <= total * ceiling + step, (prefix, cat)


def test_monthly_only_plan_still_allocates():
    plan = make_plan({}, D("50000"))
    allocation = build_allocation(
        plan=plan, prefs=AllocationPreferences(),
        temperament=TemperamentChoice.HOLD, corpus=D("600000"),
        cfg=CFG, inflation_pct=INFLATION,
    )
    total_monthly = sum((line.monthly_inr for line in allocation.lines), D(0))
    assert total_monthly == D("50000")
    assert all(line.lumpsum_inr == 0 for line in allocation.lines)
    assert any("monthly surplus" in n for n in allocation.diversification_notes)


# --- snapshots -------------------------------------------------------------


@pytest.mark.parametrize("name", list(ARCHETYPES))
def test_archetype_snapshot(name):
    allocation = build(name)
    payload = allocation.model_dump(mode="json")
    path = SNAP_DIR / f"{name}.json"
    if os.environ.get("CORPUS_REGEN_SNAPSHOTS"):
        SNAP_DIR.mkdir(exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    assert path.exists(), "snapshot missing — regenerate and hand-check it"
    assert payload == json.loads(path.read_text())
