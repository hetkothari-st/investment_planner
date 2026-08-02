"""The gate waterfall — docs/03-PLANNER-ENGINE.md. Fully deterministic.

No LLM, no market data. Strict order; each gate blocks the next:
G1 fixed -> G2 variable -> G3 buffer -> G4 high-cost debt -> G5 near goals
-> G6 temperament ceiling -> investable surplus.
"""

import math
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from corpus.planner.assumptions import Assumptions, load_assumptions
from corpus.planner.schemas import (
    GateResult,
    GateStatus,
    GoalIn,
    HorizonBucket,
    JobStability,
    PlanInput,
    PlanResult,
    SensitivityRow,
)
from corpus.planner.temperament import max_tolerable_drawdown_inr

PAISE = Decimal("0.01")


def q(v: Decimal) -> Decimal:
    return v.quantize(PAISE, rounding=ROUND_HALF_UP)



def fmt_inr(v: Decimal) -> str:
    """Indian-grouped rupees for prose: 600000 -> '6,00,000'. Whole rupees only
    in text; exact paise stay in the numeric fields."""
    whole = int(v.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    sign = "-" if whole < 0 else ""
    digits = str(abs(whole))
    if len(digits) <= 3:
        return sign + digits
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return sign + ",".join(groups) + "," + tail


def buffer_months(
    dependants: int, job_stability: JobStability, income_variability: Decimal
) -> int:
    base = 6
    if job_stability == JobStability.LOW:
        base += 3
    if job_stability == JobStability.HIGH:
        base -= 1
    base += min(dependants, 3)  # +1 per dependant, cap 3
    if income_variability > Decimal("0.25"):
        base += 2
    return max(3, min(base, 12))


def months_until(target: date, as_of: date) -> int:
    return (target.year - as_of.year) * 12 + (target.month - as_of.month)


def bucket_for_months(months: int) -> HorizonBucket:
    if months < 12:
        return HorizonBucket.LIQUID_0_12
    if months < 36:
        return HorizonBucket.DEBT_12_36
    if months < 60:
        return HorizonBucket.HYBRID_36_60
    return HorizonBucket.EQUITY_60_PLUS


def _goal_sort_key(g: GoalIn) -> tuple[int, date]:
    order = {"MUST": 0, "SHOULD": 1, "WANT": 2}
    return (order[g.priority], g.target_date)


def compute_plan(
    inp: PlanInput,
    assumptions: Assumptions | None = None,
    include_sensitivity: bool = True,
) -> PlanResult:
    a = assumptions or load_assumptions()
    p = inp.profile
    gates: list[GateResult] = []
    blocking: list[str] = []
    spending_recs: list[str] = []

    total_min_emi = q(sum((d.min_emi for d in inp.debts), Decimal(0)))
    fixed_total = q(p.fixed_outflow + total_min_emi)

    # G1 — fixed obligations
    gates.append(
        GateResult(
            gate="G1",
            label="Fixed obligations",
            status=GateStatus.PASSED,
            amount=fixed_total,
            reason=f"Rent, EMIs at minimum (₹{fmt_inr(total_min_emi)}), insurance, tax.",
        )
    )

    # G2 — variable living
    gates.append(
        GateResult(
            gate="G2",
            label="Variable living",
            status=GateStatus.PASSED,
            amount=q(p.variable_outflow),
            reason="Food, transport, utilities, discretionary.",
        )
    )

    surplus = q(p.monthly_inflow - fixed_total - p.variable_outflow)
    if surplus < 0:
        deficit = -surplus
        blocking.append(f"Spending exceeds inflow by ₹{fmt_inr(deficit)} a month.")
        spending_recs = [
            f"Monthly inflow ₹{fmt_inr(p.monthly_inflow)} does not cover ₹{fmt_inr(fixed_total)} "
            f"fixed and ₹{fmt_inr(p.variable_outflow)} variable outflow.",
            f"Reduce variable spending by at least ₹{fmt_inr(deficit)} a month, or restructure "
            "EMIs, before any investment planning is meaningful.",
        ]
        return _blocked_result(inp, a, gates, blocking, spending_recs, include_sensitivity)

    # G3 — emergency buffer
    months = buffer_months(p.dependants, p.job_stability, p.income_variability)
    monthly_essential = q(fixed_total + p.variable_outflow)
    buffer_target = q(monthly_essential * months)
    buffer_current = q(p.liquid_balance)
    buffer_funded = buffer_current >= buffer_target
    buffer_eta: int | None = None
    if not buffer_funded:
        shortfall = buffer_target - buffer_current
        buffer_eta = math.ceil(shortfall / surplus) if surplus > 0 else None
        current_months = (
            (buffer_current / monthly_essential).quantize(Decimal("0.1"))
            if monthly_essential
            else Decimal(0)
        )
        blocking.append(
            f"Emergency buffer {current_months} of {months}.0 months. "
            "Nothing invests before this."
        )
        gates.append(
            GateResult(
                gate="G3",
                label="Emergency buffer",
                status=GateStatus.BLOCKED,
                amount=surplus,
                reason=(
                    f"Target ₹{fmt_inr(buffer_target)} ({months} months of essentials); currently "
                    f"₹{fmt_inr(buffer_current)}. Entire surplus routes here"
                    + (f", full in ~{buffer_eta} months." if buffer_eta else ".")
                    + f" Keep it liquid: {a.buffer_liquid_vehicles}."
                ),
            )
        )
        return _blocked_result(
            inp, a, gates, blocking, spending_recs, include_sensitivity,
            buffer_target=buffer_target, buffer_current=buffer_current,
            buffer_eta=buffer_eta,
        )
    gates.append(
        GateResult(
            gate="G3",
            label="Emergency buffer",
            status=GateStatus.PASSED,
            amount=Decimal(0),
            reason=(
                f"Funded: ₹{fmt_inr(buffer_current)} against a ₹{fmt_inr(buffer_target)} target "
                f"({months} months)."
            ),
        )
    )

    # G4 — high-cost debt
    hurdle = a.debt_hurdle_pct.quantize(Decimal("0.1"))
    high_cost = sorted(
        (d for d in inp.debts if d.annual_rate_pct > a.debt_hurdle_pct),
        key=lambda d: d.annual_rate_pct,
        reverse=True,
    )
    if high_cost:
        worst = high_cost[0]
        blocking.append(
            f"Debt above the {hurdle}% hurdle: "
            + ", ".join(f"{d.label} at {d.annual_rate_pct}%" for d in high_cost)
            + ". Prepay before investing."
        )
        gates.append(
            GateResult(
                gate="G4",
                label="High-cost debt",
                status=GateStatus.BLOCKED,
                amount=surplus,
                reason=(
                    f"Prepaying {worst.label} at {worst.annual_rate_pct}% is a guaranteed "
                    f"{worst.annual_rate_pct}% return. Equities are assumed at "
                    f"{a.equity_nominal_pct.quantize(Decimal('0.1'))}% nominal — "
                    f"{hurdle}% after tax, with drawdown risk. Prepay first, "
                    "largest rate first."
                ),
            )
        )
        return _blocked_result(
            inp, a, gates, blocking, spending_recs, include_sensitivity,
            buffer_target=buffer_target, buffer_current=buffer_current,
        )
    gates.append(
        GateResult(
            gate="G4",
            label="High-cost debt",
            status=GateStatus.PASSED,
            amount=Decimal(0),
            reason=(
                f"No debt above the {hurdle}% hurdle"
                + (
                    ". "
                    + "; ".join(
                        f"{d.label} at {d.annual_rate_pct}% stays on schedule"
                        for d in inp.debts
                    )
                    if inp.debts
                    else "."
                )
            ),
        )
    )

    # G5 — near-dated goals earmarked from the investable lumpsum
    investable_lumpsum = q(buffer_current - buffer_target)
    buckets: dict[HorizonBucket, Decimal] = {b: Decimal(0) for b in HorizonBucket}
    remaining_lumpsum = investable_lumpsum
    earmark_notes: list[str] = []
    for goal in sorted(inp.goals, key=_goal_sort_key):
        m = months_until(goal.target_date, inp.as_of)
        bucket = bucket_for_months(m)
        take = min(remaining_lumpsum, q(goal.target_amount))
        if take > 0:
            buckets[bucket] += take
            remaining_lumpsum -= take
        if bucket in (HorizonBucket.LIQUID_0_12, HorizonBucket.DEBT_12_36):
            earmark_notes.append(
                f"{goal.label} in {m} months: ₹{fmt_inr(take)} locked to capital preservation"
                + (
                    f" (₹{fmt_inr(goal.target_amount - take)} unfunded)"
                    if take < goal.target_amount
                    else ""
                )
            )
    buckets[HorizonBucket.EQUITY_60_PLUS] += remaining_lumpsum
    gates.append(
        GateResult(
            gate="G5",
            label="Near-dated goals",
            status=GateStatus.INFO,
            amount=q(investable_lumpsum - remaining_lumpsum),
            reason=(
                "; ".join(earmark_notes)
                if earmark_notes
                else "No goals inside 36 months. The horizon rule is not binding."
            ),
        )
    )

    # G6 — temperament ceiling
    corpus = q(p.liquid_balance + p.existing_investments)
    max_dd_inr = max_tolerable_drawdown_inr(p.temperament_choice, corpus)
    if corpus > 0:
        raw_frac = max_dd_inr / (corpus * a.assumed_equity_max_dd)
        max_equity_frac = min(Decimal(1), raw_frac).quantize(Decimal("0.01"))
    else:
        max_equity_frac = Decimal(0)
    equity_capacity = buckets[HorizonBucket.EQUITY_60_PLUS]
    horizon_bound = equity_capacity < corpus * max_equity_frac
    gates.append(
        GateResult(
            gate="G6",
            label="Temperament ceiling",
            status=GateStatus.INFO,
            amount=max_dd_inr,
            reason=(
                f"A full equity drawdown is assumed at "
                f"{(a.assumed_equity_max_dd * 100).quantize(Decimal('1'))}%. Your scenario answer "
                f"tolerates a ₹{fmt_inr(max_dd_inr)} loss, capping equity at "
                f"{(max_equity_frac * 100).quantize(Decimal('1'))}% of corpus."
                + (
                    " Your stated tolerance permits more equity than your goal dates do."
                    if horizon_bound
                    else ""
                )
            ),
        )
    )

    return PlanResult(
        gates=gates,
        investable_monthly=surplus,
        investable_lumpsum=investable_lumpsum,
        buffer_target=buffer_target,
        buffer_current=buffer_current,
        buffer_eta_months=None,
        blocking_reasons=blocking,
        spending_recommendations=spending_recs,
        max_equity_fraction=max_equity_frac,
        horizon_buckets=buckets,
        assumptions_version=a.version,
        sensitivity=_sensitivity(inp, a) if include_sensitivity else [],
    )


def _blocked_result(
    inp: PlanInput,
    a: Assumptions,
    gates: list[GateResult],
    blocking: list[str],
    spending_recs: list[str],
    include_sensitivity: bool = True,
    buffer_target: Decimal = Decimal(0),
    buffer_current: Decimal = Decimal(0),
    buffer_eta: int | None = None,
) -> PlanResult:
    return PlanResult(
        gates=gates,
        investable_monthly=Decimal(0),
        investable_lumpsum=Decimal(0),
        buffer_target=buffer_target,
        buffer_current=buffer_current,
        buffer_eta_months=buffer_eta,
        blocking_reasons=blocking,
        spending_recommendations=spending_recs,
        max_equity_fraction=Decimal(0),
        horizon_buckets={b: Decimal(0) for b in HorizonBucket},
        assumptions_version=a.version,
        sensitivity=_sensitivity(inp, a) if include_sensitivity else [],
    )


def _sensitivity(inp: PlanInput, a: Assumptions) -> list[SensitivityRow]:
    """The plan is a function of assumptions, not a truth. Show it."""
    rows = []
    for real in (Decimal(5), Decimal(7), Decimal(9)):
        varied = a.model_copy(update={"equity_real_return_pct": real})
        result = compute_plan(inp, varied, include_sensitivity=False)
        base = real == a.equity_real_return_pct
        note = (
            "base plan"
            if base
            else "more to debt prepayment"
            if real < a.equity_real_return_pct
            else "more to equity"
        )
        rows.append(
            SensitivityRow(
                equity_real_return_pct=real,
                hurdle_pct=varied.debt_hurdle_pct.quantize(Decimal("0.1")),
                investable_monthly=result.investable_monthly,
                note=note,
            )
        )
    return rows
