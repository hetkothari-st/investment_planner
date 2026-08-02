# 05 — Equity Research Engine

Turns the metric spine into horizon-specific candidates with scenario bands, falsifiers,
and position sizes. This is where "act like a 30-year analyst" gets replaced by something
that actually works.

## Why roleplay fails and this doesn't

Prompting a model to "be a Wall Street veteran" produces expert-*sounding* text. Fluency
is uncorrelated with accuracy, and in finance a fluent wrong answer is worse than an
obvious wrong answer because you'll act on it.

What a real analyst actually does that's reproducible:
- computes the same 30 numbers every time and compares them to history and peers
- reads the filings for things the numbers can't show
- states what would change their mind
- sizes the position to survive being wrong

All four are implementable. The "intuition" is not, so we don't pretend to have it —
we substitute **calibration** (measured hit rate) for intuition.

## Three horizons, three different questions

| | SHORT (1–3 mo) | MID (6–18 mo) | LONG (3–7 yr) |
|---|---|---|---|
| Question | Is there a live catalyst with the market underreacting? | Are earnings estimates moving up while valuation hasn't? | Does this business compound capital? |
| Dominant metrics | momentum, relative strength, volume expansion, event proximity, liquidity | earnings revision, margin trend, valuation percentile, sector cycle | ROCE consistency, reinvestment rate, debt trend, cashflow conversion, governance |
| Cost sensitivity | **Brutal** — STCG 20% + costs | Moderate | Negligible |
| Base rate of success | Low. Expect to reject most days. | Moderate | Higher but unfalsifiable for years |
| Default posture | **Refuse unless exceptional** | Selective | Patient |

**The SHORT engine must be biased toward emitting nothing.** If on a given day the
hurdle isn't cleared, the correct output is "no short-horizon candidates today" —
and the UI must present that as a successful result, not an empty state failure.

## Scoring

```yaml
# config/weights.v1.yaml
SHORT:
  mom.rs_3m:            0.18
  mom.rs_1m:            0.12
  vol.volume_multiple:  0.14
  evt.days_to_catalyst: 0.16
  liq.adv_20d_inr:      0.10
  tech.dist_from_52w_high: 0.08
  qual.event_density:   0.12
  risk.beta_1y:        -0.10
MID:
  earn.revision_3m:     0.20
  earn.surprise_streak: 0.12
  fin.ebitda_margin_trend_4q: 0.16
  val.pe_pctl_5y:      -0.18
  val.ev_ebitda_pctl_5y: -0.12
  sec.relative_momentum: 0.12
  qual.guidance_direction: 0.10
LONG:
  fin.roce_median_5y:   0.22
  fin.roce_stability_5y: 0.14
  fin.ocf_to_ebitda_5y: 0.14
  fin.debt_to_equity_trend: -0.12
  fin.reinvestment_rate: 0.12
  gov.pledge_pct:      -0.14
  gov.related_party_ratio: -0.06
  val.pe_pctl_10y:     -0.06
```

Weights are versioned config, never code. Calibration will later tell you which version wins.

### Normalisation
Each metric → cross-sectional percentile within its sector, winsorised at 2/98.
Never raw z-scores; Indian small-cap fundamentals have vicious outliers.

### Composite → conviction
```python
conviction = (
    "HIGH"     if composite_pctl >= 90 and coverage >= 0.85 else
    "MODERATE" if composite_pctl >= 75 and coverage >= 0.70 else
    "LOW"
)
```
`coverage` = fraction of weighted metrics that were actually computable.
**Low coverage caps conviction.** A stock with missing fundamentals cannot be HIGH conviction
no matter how good its momentum looks.

## Scenario bands — how they're derived

Not from an LLM. From the stock's own realised distribution, conditioned on the setup:

```python
def scenario_band(isin, horizon_days, composite_pctl) -> Band:
    # 1. Realised return distribution over rolling `horizon_days` windows, last 5 years
    dist = rolling_forward_returns(isin, horizon_days, lookback_years=5)

    # 2. Condition on similar historical setups: windows where this stock's own
    #    composite score was in the same decile
    conditioned = dist.where(historical_composite_decile == decile(composite_pctl))
    if len(conditioned) < MIN_ANALOGUES:        # 30
        conditioned = dist                       # fall back, and flag lower confidence

    # 3. Blend with the sector's conditioned distribution (shrinkage toward peers)
    blended = shrink(conditioned, sector_dist, lam=shrinkage_lambda(len(conditioned)))

    return Band(bear=blended.q(0.20), base=blended.q(0.50), bull=blended.q(0.80))
```

The band is an **empirical quantile**, not an opinion. If the p20 is −18%, the report says
−18%, even though it's unpleasant. This alone eliminates the fantasy-target problem.

Record `n_analogues` and show it. A band from 34 analogues is worth less than one from 200.

## The cost hurdle

```python
def hurdle_pct(horizon, price, qty) -> Decimal:
    entry  = brokerage + stt_buy + exchange + gst + stamp + slippage_estimate
    exit   = brokerage + stt_sell + exchange + gst + slippage_estimate
    gross_needed = (entry + exit) / (price * qty)
    tax_rate = 0.20 if horizon == "SHORT" else 0.125
    return gross_needed / (1 - tax_rate)
```

**A candidate whose `band_base_pct` does not exceed `hurdle_pct` by a configured margin
is rejected before it ever reaches the report stage.** Log the rejection — the rejection
log is genuinely informative to read.

Slippage estimate: `max(0.05%, 0.5 × (spread_bps/10000) × sqrt(order_value / adv_20d))`.

## Falsifier generation

Every recommendation must attach ≥1 machine-checkable falsifier. Generated from templates
bound to the horizon's dominant metrics:

```python
FALSIFIER_TEMPLATES = {
  "mom.rs_3m":      lambda v: (LT, v * 0.5,  "3-month relative strength halves from entry"),
  "gov.pledge_pct": lambda v: (GT, v + 5.0,  "Promoter pledge rises 5pp above entry level"),
  "fin.ebitda_margin_ttm": lambda v: (LT, v - 2.0, "TTM EBITDA margin falls 2pp"),
  "earn.revision_3m": lambda v: (LT, 0,      "Consensus estimates turn negative"),
  "price.close":    lambda v: (LT, v * (1 + band_bear_pct/100),
                               "Price breaches the bear-case level"),
}
```

Falsifiers are evaluated nightly in pipeline step 8. On breach:
- `falsifiers.breached_at` set
- recommendation `status → INVALIDATED`
- an alert appears in the alert centre with the *original thesis line* it contradicts
- any linked `sim_position` is flagged (not auto-closed — you decide, and that decision
  is itself recorded and later scored)

**Thesis-breakage alerts, not price alerts.** A stock down 8% with an intact thesis is
noise. A stock flat with a broken thesis is urgent. Most apps get this exactly backwards.

## Position sizing

```python
def suggested_size(corpus, ann_vol_pct, band_bear_pct, max_loss_frac=0.015):
    # Size so a full bear-case realisation costs `max_loss_frac` of corpus
    loss_frac_if_bear = abs(band_bear_pct) / 100
    size = (corpus * max_loss_frac) / loss_frac_if_bear
    # Never more than 8% of corpus in one name, never below a viable ticket
    return clamp(size, MIN_TICKET_INR, corpus * 0.08)
```

Also emit `portfolio_heat`: the sum of `max_loss_frac` across all live simulated positions.
Cap it. When adding a position would push heat above 8%, the UI warns before simulation.

## Correlation / concentration check

Before presenting a candidate set, compute pairwise 1-year return correlation. If the
top-5 set has mean pairwise correlation > 0.6, insert a warning:

> These five names moved together 78% of the time over the last year. This is one bet
> in five wrappers.

Also check sector concentration and shared factor exposure (rate-sensitive, export-linked,
commodity-input).

## Candidate flow

```
universe (Nifty500 + pinned)
  → liquidity filter (adv_20d > ₹5cr, else unresearchable)
  → data-freshness filter (ohlcv <= 2 trading days stale, fundamentals <= 1 quarter stale)
  → coverage filter (>= 60% of horizon's weighted metrics computable)
  → composite scoring
  → cost-hurdle rejection
  → top N by composite (N = 8)
  → correlation prune → final 5
  → [on user open] LLM report composition
```

Steps 1–7 are nightly and cached. Step 8 is on-demand.

## Required tests

- Cost hurdle: a 1-month band of +3% on a ₹200 stock must be rejected.
- Coverage cap: a stock with 55% coverage must never reach the candidate set.
- Band sanity: for any (stock, horizon), bear < base < bull, always.
- Falsifier presence: assert every generated recommendation has ≥1 falsifier. Fail hard.
- Determinism: same inputs + same weights_version → byte-identical score_snapshot.
