# 04 — Allocation Engine

Takes `PlanResult.investable_*` and produces a ranked, **suitability-scored** list of
investment vehicles. Deterministic.

## Why this isn't a leaderboard

There is no scalar that orders FD against small-cap equity. "Best risk/return ratio" is
not a well-defined quantity — Sharpe is backward-looking, unstable, and meaningless for
an FD. So the engine produces two things:

1. **A recommended allocation** (the real answer)
2. **A per-vehicle suitability score for this user** (the browsable ranking, honestly labelled)

The ranking is a UI affordance. The allocation is the recommendation.

## Vehicle taxonomy

```yaml
vehicles:
  - id: liquid.savings
  - id: liquid.overnight_fund
  - id: liquid.fd
  - id: debt.short_duration
  - id: debt.corporate_bond
  - id: debt.gilt
  - id: hybrid.balanced_advantage
  - id: hybrid.multi_asset
  - id: equity.index_largecap
  - id: equity.index_midcap
  - id: equity.flexicap_active
  - id: equity.direct_largecap
  - id: equity.direct_midsmall
  - id: derivatives.fno            # gated OFF until module built
  - id: commodity.gold_etf
  - id: commodity.sgb
  - id: reit
  - id: invit
  - id: intl.us_index
```

Each vehicle carries declared characteristics in `config/vehicles.v1.yaml`:

```yaml
equity.direct_midsmall:
  expected_real_return_pct: 8.5
  volatility_annual_pct: 26.0
  max_historical_dd_pct: 62.0
  liquidity_days: 1
  lock_in_months: 0
  min_horizon_months: 84
  cost_drag_pct: 0.35              # brokerage + slippage, annualised
  tax:
    short_term: {rate: 0.20, threshold_months: 12}
    long_term:  {rate: 0.125, exemption_inr: 125000}
  effort: HIGH                     # research burden on the user
  knowledge_required: HIGH
```

**These are assumptions with a version number.** Show them. Let the user edit them.
When calibration data accumulates, revise them and bump the version.

## Scoring

```
suitability(v, user) =
    fit_horizon(v, user)            × w_h
  + fit_drawdown(v, user)           × w_d
  + fit_liquidity(v, user)          × w_l
  + net_expected_return(v, user)    × w_r
  + fit_effort(v, user)             × w_e
  − penalty_concentration(v, user)
```

with hard gates applied **before** scoring:

```python
HARD_GATES = [
    lambda v, u: v.min_horizon_months <= u.horizon_months,
    lambda v, u: v.lock_in_months <= u.max_lock_in_months,
    lambda v, u: v.max_historical_dd_pct * u.corpus / 100 <= u.max_tolerable_drawdown_inr,
    lambda v, u: not (v.id.startswith("equity") and u.max_equity_fraction == 0),
    lambda v, u: v.knowledge_required != "HIGH" or u.self_rated_knowledge != "LOW",
]
```

A gated-out vehicle is **shown, greyed, with the gate that killed it named**. That's more
educational than hiding it, and it prevents the user wondering why F&O never appears.

> **Implementation notes (M7).** (1) The drawdown gate evaluates at the vehicle's
> *maximum permitted weight* (the 40% single-vehicle ceiling), not at 100% of corpus:
> `dd% × 0.40 × corpus ≤ max_tolerable_drawdown_inr`. At 100% the gate would kill every
> equity vehicle (historical drawdowns 55–65%) under every temperament (max tolerated
> fraction 0.45), contradicting the reachability test below. (2) Each planner bucket is
> scored at a representative horizon: LIQUID 6, DEBT 24, HYBRID 48, EQUITY 96 months.
> (3) The monthly surplus mirrors the lumpsum bucket split; with no lumpsum it flows
> through the EQUITY_60_PLUS filling rules (recurring money is long-horizon), noted in
> the output. (4) Where the equity-index floor conflicts with the single-vehicle
> ceiling (only one index vehicle eligible), the floor wins and the output says so.
> (5) `fit_horizon` uses a declared `natural_horizon_months` per vehicle:
> `min(h/nat, nat/h)` — a savings account scores poorly for 10-year money, not just
> the reverse.

### `net_expected_return` — the honest one

```python
def net_expected_return(v, u) -> Decimal:
    gross = v.expected_real_return_pct + assumptions.inflation_expectation_pct
    after_cost = gross - v.cost_drag_pct - v.expense_ratio_pct
    tax_rate = v.tax.long_term.rate if u.horizon_months >= v.tax.short_term.threshold_months \
               else v.tax.short_term.rate
    return after_cost * (1 - tax_rate)
```

This single function is why short-horizon direct equity almost never wins. Good.

## Allocation construction

Not mean-variance optimisation. MVO on estimated returns produces garbage corner solutions
and you can't explain the output. Use **constrained bucket-filling**:

```
1. Split investable by horizon bucket (from planner G5).
2. Within each bucket, take the top-scoring eligible vehicles.
3. Apply diversification floors/ceilings:
     - no single vehicle > 40% of a bucket
     - equity bucket must contain >= 1 index vehicle at >= 50% if
       user's self_rated_knowledge is not HIGH
     - gold/commodity ceiling 15% of total
     - international ceiling 20% of total
4. Round to sensible SIP amounts (nearest ₹500).
5. Emit rationale per line, referencing the gate or score that drove it.
```

## Output

```python
class Allocation(BaseModel):
    plan_version_id: UUID
    lines: list[AllocationLine]      # vehicle_id, monthly_inr, lumpsum_inr, rationale
    ranked_vehicles: list[VehicleScore]
    gated_out: list[GateExplanation]
    assumptions_version: str
    diversification_notes: list[str]
```

## The 3D moment (justified)

The ranking view renders a **risk–return–liquidity scatter in actual 3D** (three.js).
This is not decoration: the three axes are genuinely independent and a 2D projection
loses real information. Rules:

- Orbit only. No auto-rotate. No perspective distortion of the value axes — use
  `OrthographicCamera` so equal distances mean equal quantities.
- Gated-out vehicles render as wireframe ghosts in place, so you see what you're excluded from.
- The user's recommended allocation renders as filled spheres sized by rupee amount.
- A 2D fallback table sits directly beneath it and is the accessible source of truth.
- `prefers-reduced-motion` → static isometric render, no orbit.

Everything else in the app is flat. Spend the boldness here.

## Tests

- Every vehicle must be reachable by some valid user profile (no dead entries).
- A user with 6-month horizon must never receive an equity line.
- Tax drag test: same vehicle, 11-month vs 13-month horizon, score must drop for the former.
- Snapshot test on the full allocation for three archetype profiles.
