"""Suitability scoring + constrained bucket-filling — docs/04-ALLOCATION-ENGINE.md.

Deterministic. No market data, no LLM. The ranking is a UI affordance;
the allocation is the recommendation.

Implementation note on the drawdown gate (documented in docs/04): the gate
is evaluated at the vehicle's maximum permitted weight (the 40% single-vehicle
ceiling), not at 100% of corpus. At 100% every equity vehicle (historical
drawdowns 55-65%) would be unreachable under every temperament (max tolerated
fraction 0.45), contradicting docs/04's own reachability test. At max weight
the question the gate asks stays honest: "if this line hit its historical
worst at the largest size we would ever give it, could you sit through it?"
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from corpus.allocation.schemas import (
    Allocation,
    AllocationLine,
    AllocationPreferences,
    GatedVehicle,
    Knowledge,
    VehicleScore,
)
from corpus.allocation.vehicles import Vehicle, VehicleConfig
from corpus.planner.engine import fmt_inr
from corpus.planner.schemas import HorizonBucket, PlanResult
from corpus.planner.temperament import TemperamentChoice, max_tolerable_drawdown_inr

PAISE = Decimal("0.01")
ONE = Decimal(1)
ZERO = Decimal(0)

# The horizon a bucket's money is scored at: the midpoint-ish holding period
# the bucket represents. EQUITY_60_PLUS uses 96 so that 84-month-minimum
# vehicles stay reachable (docs/04 taxonomy).
BUCKET_HORIZON_MONTHS: dict[HorizonBucket, int] = {
    HorizonBucket.LIQUID_0_12: 6,
    HorizonBucket.DEBT_12_36: 24,
    HorizonBucket.HYBRID_36_60: 48,
    HorizonBucket.EQUITY_60_PLUS: 96,
}

EFFORT_FIT = {"LOW": Decimal("1.0"), "MEDIUM": Decimal("0.6"), "HIGH": Decimal("0.25")}
DAYS_PER_MONTH = Decimal("30.4")


@dataclass(frozen=True)
class UserContext:
    """Everything the gates and fits need to know about the user."""

    horizon_months: int
    corpus: Decimal
    max_tolerable_dd_inr: Decimal
    max_equity_fraction: Decimal
    self_rated_knowledge: Knowledge
    max_lock_in_months: int | None  # None: no constraint stated


def q2(v: Decimal) -> Decimal:
    return v.quantize(PAISE, rounding=ROUND_HALF_UP)


def clamp01(v: Decimal) -> Decimal:
    return min(ONE, max(ZERO, v))


# --- hard gates (docs/04), applied before scoring -------------------------


def failed_gate(v: Vehicle, u: UserContext, cfg: VehicleConfig) -> tuple[str, str] | None:
    """First gate that kills the vehicle, or None. Order mirrors docs/04."""
    if not v.enabled:
        return ("module_disabled", v.disabled_reason or "Disabled in vehicles config.")
    if v.min_horizon_months > u.horizon_months:
        return (
            "horizon",
            f"Needs {v.min_horizon_months} months; this money has "
            f"{u.horizon_months}.",
        )
    if u.max_lock_in_months is not None and v.lock_in_months > u.max_lock_in_months:
        return (
            "lock_in",
            f"Locked for {v.lock_in_months} months against your stated maximum "
            f"of {u.max_lock_in_months}.",
        )
    worst_loss = q2(
        v.max_historical_dd_pct / 100 * cfg.construction.max_vehicle_weight * u.corpus
    )
    if u.corpus > 0 and worst_loss > u.max_tolerable_dd_inr:
        return (
            "drawdown",
            f"Historical worst is {v.max_historical_dd_pct}%. At its maximum "
            f"{cfg.construction.max_vehicle_weight:.0%} weight that is a "
            f"₹{fmt_inr(worst_loss)} loss against the "
            f"₹{fmt_inr(u.max_tolerable_dd_inr)} your scenario answer tolerates.",
        )
    if v.id.startswith("equity") and u.max_equity_fraction == 0:
        return ("equity_zero", "Your temperament ceiling puts equity at 0%.")
    if v.knowledge_required == "HIGH" and u.self_rated_knowledge == Knowledge.LOW:
        return (
            "knowledge",
            "Needs HIGH self-rated knowledge; yours is LOW. Change it in "
            "preferences if that is wrong.",
        )
    return None


# --- fits + suitability ----------------------------------------------------


def net_expected_return(v: Vehicle, horizon_months: int, inflation_pct: Decimal) -> Decimal:
    """docs/04: gross nominal, minus costs, times (1 - applicable tax rate).

    This single function is why short-horizon direct equity almost never wins.
    """
    gross = v.expected_real_return_pct + inflation_pct
    after_cost = gross - v.cost_drag_pct - v.expense_ratio_pct
    threshold = v.tax.short_term.threshold_months or 0
    rate = v.tax.long_term.rate if horizon_months >= threshold else v.tax.short_term.rate
    return (after_cost * (1 - rate)).quantize(PAISE, rounding=ROUND_HALF_UP)


def fits(
    v: Vehicle, u: UserContext, cfg: VehicleConfig, inflation_pct: Decimal
) -> dict[str, Decimal]:
    h = Decimal(max(u.horizon_months, 1))
    nat = Decimal(max(v.natural_horizon_months, 1))
    fit_horizon = clamp01(min(h / nat, nat / h))

    if u.corpus > 0 and u.max_tolerable_dd_inr > 0:
        worst = v.max_historical_dd_pct / 100 * cfg.construction.max_vehicle_weight * u.corpus
        fit_drawdown = clamp01(ONE - worst / u.max_tolerable_dd_inr)
    else:
        fit_drawdown = ONE if v.max_historical_dd_pct == 0 else ZERO

    # worst-case days to cash: settlement plus any hard lock
    days_to_cash = Decimal(v.liquidity_days) + Decimal(v.lock_in_months) * DAYS_PER_MONTH
    fit_liquidity = clamp01(ONE - days_to_cash / Decimal(365))

    ner = net_expected_return(v, u.horizon_months, inflation_pct)
    fit_return = clamp01(ner / cfg.scoring.return_norm_pct)

    fit_effort = EFFORT_FIT[v.effort]
    return {
        "fit_horizon": fit_horizon.quantize(Decimal("0.0001")),
        "fit_drawdown": fit_drawdown.quantize(Decimal("0.0001")),
        "fit_liquidity": fit_liquidity.quantize(Decimal("0.0001")),
        "fit_return": fit_return.quantize(Decimal("0.0001")),
        "fit_effort": fit_effort,
    }


def suitability_pct(components: dict[str, Decimal], cfg: VehicleConfig) -> Decimal:
    w = cfg.scoring
    score = (
        w.w_horizon * components["fit_horizon"]
        + w.w_drawdown * components["fit_drawdown"]
        + w.w_liquidity * components["fit_liquidity"]
        + w.w_return * components["fit_return"]
        + w.w_effort * components["fit_effort"]
    )
    return (score * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


# --- constrained bucket-filling (docs/04: not MVO, on purpose) -------------


def _round_conserving(
    raw: dict[str, Decimal], step: Decimal, total: Decimal
) -> dict[str, Decimal]:
    """Round lines to SIP-sized steps; the largest line absorbs the remainder
    so the sum equals `total` exactly. Conservation beats roundness."""
    if not raw or total <= 0:
        return {}
    largest = max(raw, key=lambda k: (raw[k], k))
    out: dict[str, Decimal] = {}
    for k, v in raw.items():
        if k == largest:
            continue
        r = (v / step).quantize(Decimal(0), rounding=ROUND_HALF_UP) * step
        if r > 0:
            out[k] = q2(r)
    out[largest] = q2(total - sum(out.values(), ZERO))
    return out


def _category(vehicle_id: str) -> str:
    return vehicle_id.split(".", 1)[0]


def _fill_bucket(
    bucket: HorizonBucket,
    amount: Decimal,
    scored: list[tuple[Vehicle, Decimal, dict[str, Decimal]]],
    u: UserContext,
    cfg: VehicleConfig,
    category_room: dict[str, Decimal],
    notes: list[str],
) -> dict[str, Decimal]:
    """Top-scoring eligible vehicles, 40% single-vehicle ceiling, index floor
    in the equity bucket, global commodity/intl ceilings. Deterministic."""
    cap = amount * cfg.construction.max_vehicle_weight
    shares: dict[str, Decimal] = {}
    remaining = amount

    def give(v: Vehicle, want: Decimal) -> Decimal:
        nonlocal remaining
        room = want
        cat = _category(v.id)
        if cat in category_room:
            room = min(room, category_room[cat])
        take = q2(min(room, remaining))
        if take <= 0:
            return ZERO
        shares[v.id] = shares.get(v.id, ZERO) + take
        remaining = q2(remaining - take)
        if cat in category_room:
            category_room[cat] = q2(category_room[cat] - take)
        return take

    if bucket == HorizonBucket.EQUITY_60_PLUS and u.self_rated_knowledge != Knowledge.HIGH:
        index = [s for s in scored if s[0].id.startswith("equity.index")]
        if index:
            floor_left = amount * cfg.construction.index_floor
            for v, _, _ in index:
                if floor_left <= 0:
                    break
                want = min(cap, floor_left)
                if len(index) == 1 and floor_left > cap:
                    # floor beats the single-vehicle ceiling; docs/04 lists both,
                    # the floor is the safety rule so it wins
                    want = floor_left
                    notes.append(
                        f"{v.label}: index floor {cfg.construction.index_floor:.0%} "
                        "overrides the single-vehicle ceiling (only one index "
                        "vehicle is eligible)."
                    )
                floor_left -= give(v, want)

    for v, _, _ in scored:
        if remaining <= 0:
            break
        give(v, cap - shares.get(v.id, ZERO))

    if remaining > 0 and scored:
        # every eligible vehicle is at a ceiling; park the rest in the top one
        top = scored[0][0]
        shares[top.id] = shares.get(top.id, ZERO) + remaining
        notes.append(
            f"{bucket.value}: ceilings left ₹{fmt_inr(remaining)} unplaced; it "
            f"sits in {top.label} above its ceiling rather than being hidden."
        )
        remaining = ZERO
    return shares


def build_allocation(
    plan: PlanResult,
    prefs: AllocationPreferences,
    temperament: TemperamentChoice,
    corpus: Decimal,
    cfg: VehicleConfig,
    inflation_pct: Decimal,
) -> Allocation:
    max_dd_inr = max_tolerable_drawdown_inr(temperament, corpus)
    notes: list[str] = []

    def ctx(horizon_months: int) -> UserContext:
        return UserContext(
            horizon_months=horizon_months,
            corpus=corpus,
            max_tolerable_dd_inr=max_dd_inr,
            max_equity_fraction=plan.max_equity_fraction,
            self_rated_knowledge=prefs.self_rated_knowledge,
            max_lock_in_months=prefs.max_lock_in_months,
        )

    def eligible_scored(u: UserContext) -> list[tuple[Vehicle, Decimal, dict[str, Decimal]]]:
        rows = []
        for v in cfg.vehicles:
            if failed_gate(v, u, cfg) is not None:
                continue
            comps = fits(v, u, cfg, inflation_pct)
            rows.append((v, suitability_pct(comps, cfg), comps))
        rows.sort(key=lambda r: (-r[1], r[0].id))
        return rows

    buckets = {b: Decimal(v) for b, v in plan.horizon_buckets.items()}
    total_lumpsum = sum(buckets.values(), ZERO)
    monthly = Decimal(plan.investable_monthly)

    # Monthly surplus is recurring, long-horizon money. When there is no
    # lumpsum to mirror, it flows through the equity bucket's filling rules.
    synthetic_monthly_only = total_lumpsum == 0 and monthly > 0
    if synthetic_monthly_only:
        buckets[HorizonBucket.EQUITY_60_PLUS] = monthly
        total_lumpsum = monthly
        notes.append(
            "No investable lumpsum: the monthly surplus is allocated with "
            "long-horizon (EQUITY_60_PLUS) rules, since recurring money "
            "compounds across the full horizon."
        )

    category_room = {
        "commodity": q2(total_lumpsum * cfg.construction.gold_ceiling),
        "intl": q2(total_lumpsum * cfg.construction.intl_ceiling),
    }

    # fill each bucket at its own horizon
    bucket_shares: dict[HorizonBucket, dict[str, Decimal]] = {}
    bucket_rank: dict[HorizonBucket, list[str]] = {}
    for bucket in HorizonBucket:
        amount = buckets.get(bucket, ZERO)
        if amount <= 0:
            continue
        u = ctx(BUCKET_HORIZON_MONTHS[bucket])
        scored = eligible_scored(u)
        bucket_rank[bucket] = [v.id for v, _, _ in scored]
        raw = _fill_bucket(bucket, amount, scored, u, cfg, category_room, notes)
        bucket_shares[bucket] = _round_conserving(
            raw, cfg.construction.sip_round_inr, amount
        )

    # monthly mirrors the lumpsum split (same vehicles, same proportions)
    lines: list[AllocationLine] = []
    lumpsum_by_vehicle: dict[str, Decimal] = {}
    monthly_by_vehicle: dict[str, Decimal] = {}
    if total_lumpsum > 0:
        raw_monthly = {
            f"{b.value}:{vid}": monthly * amt / total_lumpsum
            for b, shares in bucket_shares.items()
            for vid, amt in shares.items()
        }
        rounded_monthly = _round_conserving(
            raw_monthly, cfg.construction.sip_round_inr, monthly
        )
    else:
        rounded_monthly = {}

    for bucket, shares in bucket_shares.items():
        u_h = BUCKET_HORIZON_MONTHS[bucket]
        for rank, vid in enumerate(bucket_rank[bucket], start=1):
            if vid not in shares:
                continue
            v = cfg.by_id(vid)
            lump = ZERO if synthetic_monthly_only else shares[vid]
            per_month = (
                shares[vid]
                if synthetic_monthly_only
                else rounded_monthly.get(f"{bucket.value}:{vid}", ZERO)
            )
            ner = net_expected_return(v, u_h, inflation_pct)
            lines.append(
                AllocationLine(
                    vehicle_id=vid,
                    label=v.label,
                    bucket=bucket,
                    lumpsum_inr=lump,
                    monthly_inr=per_month,
                    rationale=(
                        f"#{rank} by suitability in {bucket.value}; net expected "
                        f"{ner}%/yr after cost and tax at {u_h} months."
                    ),
                )
            )
            lumpsum_by_vehicle[vid] = lumpsum_by_vehicle.get(vid, ZERO) + lump
            monthly_by_vehicle[vid] = monthly_by_vehicle.get(vid, ZERO) + per_month
        # any allocated vehicle that fell out of rank list (parked remainder)
        for vid, amt in shares.items():
            if vid not in bucket_rank[bucket]:
                v = cfg.by_id(vid)
                lines.append(
                    AllocationLine(
                        vehicle_id=vid, label=v.label, bucket=bucket,
                        lumpsum_inr=amt, monthly_inr=ZERO,
                        rationale="Remainder line (see diversification notes).",
                    )
                )
                lumpsum_by_vehicle[vid] = lumpsum_by_vehicle.get(vid, ZERO) + amt

    # ranked list + gate explanations at the user's effective horizon:
    # the farthest bucket actually holding money
    active = [b for b, amt in buckets.items() if amt > 0]
    effective_h = max(
        (BUCKET_HORIZON_MONTHS[b] for b in active),
        default=BUCKET_HORIZON_MONTHS[HorizonBucket.EQUITY_60_PLUS],
    )
    u_eff = ctx(effective_h)
    ranked: list[VehicleScore] = []
    gated: list[GatedVehicle] = []
    for v in cfg.vehicles:
        failure = failed_gate(v, u_eff, cfg)
        ner = net_expected_return(v, effective_h, inflation_pct)
        if failure is None:
            comps = fits(v, u_eff, cfg, inflation_pct)
            ranked.append(
                VehicleScore(
                    vehicle_id=v.id,
                    label=v.label,
                    suitability_pct=suitability_pct(comps, cfg),
                    components=comps,
                    net_expected_return_pct=ner,
                    volatility_annual_pct=v.volatility_annual_pct,
                    liquidity_days=v.liquidity_days,
                    lock_in_months=v.lock_in_months,
                    effort=v.effort,
                    knowledge_required=v.knowledge_required,
                    allocated_lumpsum=lumpsum_by_vehicle.get(v.id, ZERO),
                    allocated_monthly=monthly_by_vehicle.get(v.id, ZERO),
                )
            )
        else:
            gate, explanation = failure
            gated.append(
                GatedVehicle(
                    vehicle_id=v.id,
                    label=v.label,
                    gate=gate,
                    explanation=explanation,
                    net_expected_return_pct=ner,
                    volatility_annual_pct=v.volatility_annual_pct,
                    liquidity_days=v.liquidity_days,
                    lock_in_months=v.lock_in_months,
                )
            )
    ranked.sort(key=lambda r: (-r.suitability_pct, r.vehicle_id))

    return Allocation(
        plan_version_id=plan.version_id,
        horizon_months=effective_h,
        lines=lines,
        ranked_vehicles=ranked,
        gated_out=gated,
        vehicles_version=cfg.version,
        assumptions_version=plan.assumptions_version,
        diversification_notes=notes,
        preferences=prefs,
    )
