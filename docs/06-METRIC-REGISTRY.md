# 06 — Metric Registry

The single source of truth for every number the system can display.
**If a `field_id` is not in this file, no part of the system may emit it.**

Implemented in `corpus/metrics/registry.py` as a frozen dict. Add a test that asserts
the registry keys match this document exactly — the doc and the code drift otherwise.

```python
@dataclass(frozen=True)
class MetricSpec:
    field_id: str
    label: str              # what the UI shows
    unit: Literal["pct","ratio","x","inr","inr_cr","days","score","count"]
    precision: int
    higher_is_better: bool | None   # None = context-dependent
    min_history_days: int
    sources: tuple[str, ...]
    formula_note: str
```

---

## price.* — raw price facts

| field_id | label | unit | notes |
|---|---|---|---|
| `price.close` | Close | inr | Latest adjusted close |
| `price.52w_high` | 52-week high | inr | |
| `price.52w_low` | 52-week low | inr | |
| `tech.dist_from_52w_high` | Off 52-week high | pct | Negative = below |
| `tech.dist_from_52w_low` | Above 52-week low | pct | |

## mom.* — momentum

| field_id | label | unit | notes |
|---|---|---|---|
| `mom.ret_1m` | 1-month return | pct | |
| `mom.ret_3m` | 3-month return | pct | |
| `mom.ret_6m` | 6-month return | pct | |
| `mom.ret_12m_ex1m` | 12-month return (ex last month) | pct | Classic momentum; skips reversal month |
| `mom.rs_1m` | Relative strength 1m | pct | vs NIFTY 500 |
| `mom.rs_3m` | Relative strength 3m | pct | vs NIFTY 500 |
| `mom.rs_sector_3m` | Relative strength vs sector | pct | |
| `mom.consistency_6m` | Momentum consistency | ratio | Fraction of weeks with positive RS |

## vol.* / risk.*

| field_id | label | unit | notes |
|---|---|---|---|
| `risk.vol_ann_1y` | Annualised volatility | pct | stdev of daily log returns × √252 |
| `risk.beta_1y` | Beta | x | vs NIFTY 50, 1y daily |
| `risk.max_dd_3y` | Max drawdown (3y) | pct | |
| `risk.downside_dev_1y` | Downside deviation | pct | |
| `risk.ulcer_index_1y` | Ulcer index | score | Depth×duration of drawdowns |
| `vol.volume_multiple` | Volume vs 20d average | x | Latest volume / ADV20 |
| `vol.obv_slope_3m` | On-balance-volume slope | score | |

## liq.* — liquidity (gates researchability)

| field_id | label | unit | notes |
|---|---|---|---|
| `liq.adv_20d_inr` | 20-day avg traded value | inr_cr | Hard filter at ₹5cr |
| `liq.spread_bps_est` | Estimated spread | ratio | From intraday if available, else proxy |
| `liq.impact_cost_1l` | Impact cost, ₹1L order | pct | |
| `liq.days_to_exit` | Days to exit position | days | position_value / (0.10 × ADV) |

## val.* — valuation, always as percentile of own history

Absolute P/E is meaningless across sectors. Percentiles are comparable.

| field_id | label | unit | notes |
|---|---|---|---|
| `val.pe_ttm` | P/E (TTM) | x | Shown but never scored directly |
| `val.pe_pctl_5y` | P/E percentile (5y own history) | pct | Lower = cheaper vs own past |
| `val.pe_pctl_10y` | P/E percentile (10y) | pct | Needs 10y history |
| `val.pe_pctl_sector` | P/E percentile vs sector | pct | |
| `val.ev_ebitda_pctl_5y` | EV/EBITDA percentile | pct | |
| `val.pb_pctl_5y` | P/B percentile | pct | |
| `val.ev_sales_pctl_5y` | EV/Sales percentile | pct | For pre-profit names |
| `val.earnings_yield_spread` | Earnings yield − 10y G-sec | pct | The one absolute valuation measure worth keeping |

## fin.* — fundamentals

| field_id | label | unit | notes |
|---|---|---|---|
| `fin.revenue_cagr_3y` | Revenue CAGR (3y) | pct | |
| `fin.revenue_cagr_5y` | Revenue CAGR (5y) | pct | |
| `fin.ebitda_margin_ttm` | EBITDA margin (TTM) | pct | |
| `fin.ebitda_margin_trend_4q` | Margin trend (4 quarters) | pct | Linear slope, pp per quarter |
| `fin.pat_cagr_3y` | PAT CAGR (3y) | pct | |
| `fin.roce_ttm` | ROCE (TTM) | pct | EBIT / (equity + debt − cash) |
| `fin.roce_median_5y` | ROCE median (5y) | pct | Median beats mean here |
| `fin.roce_stability_5y` | ROCE stability | score | 1 − (stdev/median), clipped [0,1] |
| `fin.roe_ttm` | ROE (TTM) | pct | |
| `fin.debt_to_equity` | Debt / equity | x | |
| `fin.debt_to_equity_trend` | D/E trend (8q) | x | Slope |
| `fin.interest_coverage` | Interest coverage | x | EBIT / interest |
| `fin.ocf_to_ebitda_5y` | Cash conversion (5y) | ratio | **The most underrated metric here.** |
| `fin.fcf_yield` | FCF yield | pct | |
| `fin.reinvestment_rate` | Reinvestment rate | pct | (capex − dep) / EBIT |
| `fin.working_capital_days` | Working capital cycle | days | |
| `fin.wc_days_trend_4q` | WC cycle trend | days | Rising = warning |

## earn.* — earnings dynamics

| field_id | label | unit | notes |
|---|---|---|---|
| `earn.surprise_last` | Last quarter surprise | pct | vs consensus if available, else vs 4q trend |
| `earn.surprise_streak` | Consecutive beats | count | |
| `earn.revision_3m` | Estimate revision (3m) | pct | Requires estimates source; may be null |
| `earn.days_since_result` | Days since last result | days | |
| `earn.days_to_next_result` | Days to next result | days | From filing calendar |

## gov.* — governance (long-horizon weight, hard flags)

| field_id | label | unit | notes |
|---|---|---|---|
| `gov.promoter_pct` | Promoter holding | pct | |
| `gov.pledge_pct` | Promoter pledge | pct | **> 20% is a hard warning at any horizon** |
| `gov.pledge_trend_4q` | Pledge trend | pct | |
| `gov.fii_pct` | FII holding | pct | |
| `gov.fii_trend_4q` | FII trend | pct | |
| `gov.dii_trend_4q` | DII trend | pct | |
| `gov.auditor_change_24m` | Auditor changed (24m) | count | Any value > 0 is a flag |
| `gov.related_party_ratio` | Related-party txn / revenue | pct | |
| `gov.contingent_liab_ratio` | Contingent liabilities / networth | pct | |

## sec.* — sector context

| field_id | label | unit |
|---|---|---|
| `sec.relative_momentum` | Sector RS vs NIFTY 500 (3m) | pct |
| `sec.valuation_pctl` | Sector valuation percentile | pct |
| `sec.breadth` | % of sector above 50-DMA | pct |

## evt.* / qual.* — event and qualitative

| field_id | label | unit | notes |
|---|---|---|---|
| `evt.days_to_catalyst` | Days to next known catalyst | days | Results, ex-date, listing, regulatory |
| `qual.event_density` | Material filings (90d) | count | Derived from `qual_facts` |
| `qual.guidance_direction` | Guidance direction | score | −1/0/+1 from extracted facts |
| `qual.negative_fact_count` | Negative material facts (180d) | count | |

## cost.* — computed per candidate, not per stock

| field_id | label | unit |
|---|---|---|
| `cost.hurdle_pct` | Break-even hurdle after costs & tax | pct |
| `cost.slippage_est_pct` | Estimated slippage | pct |
| `cost.round_trip_inr` | Round-trip cost | inr |

## meta.* — always shown alongside any report

| field_id | label | unit | notes |
|---|---|---|---|
| `meta.coverage` | Metric coverage | pct | Fraction computable |
| `meta.n_analogues` | Historical analogues used for band | count | |
| `meta.data_as_of` | Data current as of | — | Date |
| `meta.oldest_input_age` | Oldest input age | days | The honest staleness number |

---

## Rules

1. A metric returning `None` writes a `metric_gaps` row with a reason. Never a default.
2. Percentile metrics require `min_history_days`; below it, return `None`, not a partial percentile.
3. Every metric function is pure and has a golden test with hand-verified expected output.
4. Adding a metric requires: registry entry + this doc + test + a note in the weights config
   (even if weight is 0).
5. Renaming a `field_id` is a breaking change — old `recommendations.score_snapshot` rows
   reference it. Add new, deprecate old, never rename in place.
