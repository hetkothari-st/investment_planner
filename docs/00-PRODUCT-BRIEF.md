# 00 — Product Brief

## What this is

A personal investment research system that does three jobs, in order:

1. **Plan** — decides how much money should be invested at all, before touching markets.
2. **Allocate** — ranks investment vehicles by suitability *for this person's actual numbers*.
3. **Research** — for equities, produces horizon-specific, falsifiable, scored theses.

And one job that runs underneath all of them:

4. **Keep score** — every output is logged, frozen, and graded when its horizon expires.

## The core argument

Consumer investing apps optimise for confidence. This one optimises for **calibration**.

A recommendation that says "+25% next month" is worthless even when it's right, because
you can't tell it apart from luck. A recommendation that says "+6–10% over 3 months if
margin expansion holds; dead if Q2 EBITDA margin < 14%" is auditable — and the system
that produced it can be graded.

Everything in the architecture follows from that: the deterministic/LLM split, the
metric registry, the frozen recommendation snapshots, the calibration ledger.

## Non-goals — do not build these

- Multi-user, roles, org accounts, billing, onboarding funnels
- Any compliance, disclaimer, KYC, or advisory-licence surface
- Order placement. **The system never places a real trade.** Simulation only.
- Social features, leaderboards, sharing, copy-trading
- Push notifications to mobile (in-app alert centre only)
- Point price predictions of any kind
- Any "AI confidence score" that isn't derived from measured historical hit rate

## The five design commitments

**1. Numbers are computed, prose is written.**
The LLM has no arithmetic authority. Structural, enforced by the report contract.

**2. Every thesis has a kill condition.**
If you can't state what would make it wrong, you don't have a thesis, you have a vibe.
The engine refuses to emit a recommendation without at least one machine-checkable falsifier.

**3. Cost and tax are modelled, not mentioned.**
Brokerage, STT, exchange charges, stamp duty, GST, slippage, and STCG/LTCG are subtracted
before a suggestion is scored. Short-horizon ideas must clear a much higher bar. Most won't.
That's the correct outcome.

**4. Sizing is part of the recommendation.**
"Buy X" is incomplete. "₹18,000 of X — the size at which a full thesis failure costs
1.5% of corpus, given 34% annualised vol" is a recommendation.

**5. The system publishes its own hit rate.**
Prominently. On the dashboard. Broken down by horizon. Including the horizons where it's bad.

## User model

One person. Known. Their state:

```
identity      → nothing beyond a display name
cashflow      → monthly inflow, fixed outflow, variable outflow, irregular obligations
balance sheet → liquid balance, existing investments, debts (with rates), insurance cover
constraints   → known goals with dates and amounts, dependants, job stability (self-rated)
temperament   → max tolerable drawdown, stated in rupees not percent (people lie in percent)
```

Temperament is elicited by scenario, not by a slider:
*"Your ₹5,00,000 becomes ₹3,40,000 over four months. What do you do?"* — with concrete
options. A slider labelled "risk appetite 1–10" produces a number that means nothing.

## Vocabulary (use these exact words in UI copy)

| Use | Not |
|---|---|
| Thesis | Recommendation, Signal, Pick |
| Falsifier | Stop loss, Risk |
| Horizon | Timeframe, Duration |
| Simulated position | Paper trade, Virtual portfolio |
| Measured / Inferred | AI-generated, Smart |
| Calibration | Accuracy, Performance |
| Scenario band | Target, Prediction |

Copy register: plain, direct, no exclamation marks, no encouragement.
The interface is a colleague who's read the filings, not a coach.
