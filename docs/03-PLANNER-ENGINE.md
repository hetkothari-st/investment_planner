# 03 — Planner Engine

The layer that runs **before** any investment type is shown. Fully deterministic.
No LLM, no market data. This is the highest-value, lowest-risk module — build it first.

## What it answers

> Given your income, spending, debts, buffer and obligations — how much money should
> reach a market at all, and in what order should everything else be paid?

## The waterfall (strict order, each gate blocks the next)

```
INFLOW (monthly)
   │
   ├─► [G1] Fixed obligations          rent, EMIs at minimum, insurance premiums, tax
   │
   ├─► [G2] Variable living            food, transport, utilities, discretionary
   │
   ├─► [G3] Emergency buffer           until target reached — NOTHING invests before this
   │        target = months_required × (fixed + variable)
   │
   ├─► [G4] High-cost debt             every debt above the hurdle rate, largest rate first
   │
   ├─► [G5] Near-dated goals           any goal < 36 months → capital-preservation only
   │
   └─► [G6] Investable surplus         ← the only money the allocation engine ever sees
```

### G3 — emergency buffer sizing

```python
def buffer_months(dependants: int, job_stability: JobStability,
                  income_variability: Decimal) -> int:
    base = 6
    if job_stability == "LOW":    base += 3
    if job_stability == "HIGH":   base -= 1
    base += min(dependants, 3)                      # +1 per dependant, cap 3
    if income_variability > Decimal("0.25"):         # stdev/mean of last 12 months
        base += 2
    return max(3, min(base, 12))
```

Buffer lives in liquid instruments only: sweep-in FD, overnight/liquid fund, savings.
The planner names the vehicle; it does not treat the buffer as an "investment".

### G4 — the debt hurdle

The hurdle is not a fixed number. It's the honest comparison:

```
hurdle_rate = expected_real_equity_return_after_tax
            ≈ nominal_equity_expectation (7.0% real + inflation)
              × (1 - effective_tax_drag)
```

Default assumption set (put these in `config/assumptions.v1.yaml`, never inline):

```yaml
inflation_expectation_pct: 5.0
equity_real_return_pct: 7.0            # long-run, deliberately conservative
debt_return_pct: 6.5
gold_real_return_pct: 1.5
effective_ltcg_drag: 0.125
effective_stcg_drag: 0.20
confidence: "These are assumptions, not forecasts. Shown to the user as such."
```

Any debt whose rate exceeds `hurdle_rate` gets prepaid before investing.
Personal loans and credit cards always will. Home loans usually won't.
**Show the arithmetic.** "Prepaying at 13.5% is a guaranteed 13.5% return.
Equities are assumed at 12.4% nominal, before tax, with drawdown risk. Prepay first."

### G5 — the horizon rule

```
< 12 months   → savings / liquid fund / FD only
12–36 months  → debt funds, short-duration, arbitrage; no equity
36–60 months  → hybrid, max 40% equity
> 60 months   → equity permitted up to temperament ceiling
```

This is non-negotiable and overrides everything the allocation engine wants to do.

### G6 — temperament ceiling

Elicited by scenario (see brief). Convert the answer into a max drawdown in rupees,
then back into a maximum equity fraction:

```python
max_equity_frac = max_tolerable_drawdown_inr / (corpus * ASSUMED_EQUITY_MAX_DD)
# ASSUMED_EQUITY_MAX_DD = 0.45  (Indian large-cap has done worse; be honest about that)
```

If the user's stated tolerance implies 90% equity, cap at the horizon rule anyway
and say so: *"Your stated tolerance permits more equity than your goal dates do."*

## Output shape

```python
class PlanResult(BaseModel):
    version_id: UUID
    generated_at: datetime
    gates: list[GateResult]           # each with status, amount, reason
    investable_monthly: Decimal
    investable_lumpsum: Decimal
    buffer_target: Decimal
    buffer_current: Decimal
    buffer_eta_months: int | None
    blocking_reasons: list[str]       # e.g. "Emergency buffer 3.2 of 6.0 months"
    max_equity_fraction: Decimal
    horizon_buckets: dict[str, Decimal]
    assumptions_version: str
```

`blocking_reasons` is the important field. When it's non-empty, the allocation screen
renders in a locked state with the reason printed. Do not let the user click past it
into stock research — that's the whole point of the gate.

## Sensitivity view

Every plan ships with a small sensitivity table, because the assumptions are guesses:

| If equity real return is | Prepay threshold becomes | Your ₹X/mo split becomes |
|---|---|---|
| 5% | 11.0% | more to debt |
| 7% (base) | 12.4% | base plan |
| 9% | 13.9% | more to equity |

This teaches the user that the plan is a function of assumptions, not a truth.

## What the planner must never do

- Recommend insurance products as investments (ULIP, endowment). If detected in existing
  holdings, flag the cost drag explicitly.
- Assume a tax regime. Ask which one, compute under both if unsure.
- Produce a single "score" for financial health. Gates and amounts, not gamification.

## Tests required

Golden cases in `tests/planner/cases/*.yaml`, each with input profile and expected gates:
1. High income, no debt, no buffer → everything to buffer, zero investable
2. Buffer full, 14% personal loan → all surplus to debt, zero investable
3. Buffer full, only 8.4% home loan → invests, prepayment not recommended
4. Goal in 18 months for 60% of corpus → equity locked out for that portion
5. Negative surplus → plan returns spending-side recommendations only
