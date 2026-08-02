"""The five golden cases from docs/03 — the M3 acceptance criterion."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from corpus.planner.engine import compute_plan
from corpus.planner.schemas import PlanInput

CASES_DIR = Path(__file__).parent / "cases"
AS_OF = date(2026, 7, 31)


def load_cases():
    return [
        pytest.param(yaml.safe_load(path.read_text()), id=path.stem)
        for path in sorted(CASES_DIR.glob("*.yaml"))
    ]


@pytest.mark.parametrize("case", load_cases())
def test_golden_case(case):
    inp = PlanInput(
        profile=case["profile"], debts=case["debts"], goals=case["goals"], as_of=AS_OF
    )
    result = compute_plan(inp)
    expect = case["expect"]

    if "investable_monthly" in expect:
        assert result.investable_monthly == Decimal(expect["investable_monthly"])
    if "investable_lumpsum" in expect:
        assert result.investable_lumpsum == Decimal(expect["investable_lumpsum"])
    if "buffer_eta_months" in expect:
        assert result.buffer_eta_months == expect["buffer_eta_months"]

    gates = {g.gate: g for g in result.gates}
    for gate, status in expect.get("gate_status", {}).items():
        assert gates[gate].status == status, f"{gate}: {gates[gate]}"
    for gate, fragment in expect.get("gate_reason_contains", {}).items():
        assert fragment in gates[gate].reason, gates[gate].reason

    if "blocking_contains" in expect:
        assert any(expect["blocking_contains"] in b for b in result.blocking_reasons), (
            result.blocking_reasons
        )
    if expect.get("blocking_empty"):
        assert result.blocking_reasons == []
    if "spending_recommendations_min" in expect:
        assert len(result.spending_recommendations) >= expect["spending_recommendations_min"]

    for bucket, amount in expect.get("bucket", {}).items():
        assert result.horizon_buckets[bucket] == Decimal(amount), result.horizon_buckets

    # Invariants that hold for every case
    if result.blocking_reasons:
        assert result.investable_monthly == 0, (
            "blocking reasons must imply zero investable"
        )
    assert result.sensitivity, "every plan ships with its sensitivity table"
    assert result.assumptions_version == "v1"


def test_fmt_inr_indian_grouping():
    from decimal import Decimal

    from corpus.planner.engine import fmt_inr

    assert fmt_inr(Decimal("600000")) == "6,00,000"
    assert fmt_inr(Decimal("1234567.89")) == "12,34,568"
    assert fmt_inr(Decimal("999")) == "999"
    assert fmt_inr(Decimal("-40000")) == "-40,000"
