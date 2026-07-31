"""The metric registry — the single source of truth for every number the
system can display. If a field_id is not here, no part of the system may emit
it. A test asserts this file matches docs/06-METRIC-REGISTRY.md exactly.
"""

from dataclasses import dataclass
from typing import Literal

Unit = Literal["pct", "ratio", "x", "inr", "inr_cr", "days", "score", "count", "date"]


@dataclass(frozen=True)
class MetricSpec:
    field_id: str
    label: str
    unit: Unit
    precision: int
    higher_is_better: bool | None  # None = context-dependent
    min_history_days: int
    sources: tuple[str, ...]
    formula_note: str


def _spec(
    field_id: str,
    label: str,
    unit: Unit,
    precision: int = 4,
    higher_is_better: bool | None = None,
    min_history_days: int = 0,
    sources: tuple[str, ...] = ("kite",),
    formula_note: str = "",
) -> tuple[str, MetricSpec]:
    return field_id, MetricSpec(
        field_id, label, unit, precision, higher_is_better, min_history_days,
        sources, formula_note,
    )


REGISTRY: dict[str, MetricSpec] = dict(
    [
        # price.* — raw price facts
        _spec("price.close", "Close", "inr", 4, None, 1, ("kite",), "Latest adjusted close"),
        _spec("price.52w_high", "52-week high", "inr", 4, None, 252),
        _spec("price.52w_low", "52-week low", "inr", 4, None, 252),
        _spec("tech.dist_from_52w_high", "Off 52-week high", "pct", 4, None, 252,
              ("kite",), "Negative = below"),
        _spec("tech.dist_from_52w_low", "Above 52-week low", "pct", 4, None, 252),
        # mom.*
        _spec("mom.ret_1m", "1-month return", "pct", 4, True, 22),
        _spec("mom.ret_3m", "3-month return", "pct", 4, True, 64),
        _spec("mom.ret_6m", "6-month return", "pct", 4, True, 127),
        _spec("mom.ret_12m_ex1m", "12-month return (ex last month)", "pct", 4, True, 253,
              ("kite",), "Classic momentum; skips the reversal month"),
        _spec("mom.rs_1m", "Relative strength 1m", "pct", 4, True, 22, ("kite",), "vs NIFTY 500"),
        _spec("mom.rs_3m", "Relative strength 3m", "pct", 4, True, 64, ("kite",), "vs NIFTY 500"),
        _spec("mom.rs_sector_3m", "Relative strength vs sector", "pct", 4, True, 64),
        _spec("mom.consistency_6m", "Momentum consistency", "ratio", 4, True, 127,
              ("kite",), "Fraction of weeks with positive RS"),
        # vol.* / risk.*
        _spec("risk.vol_ann_1y", "Annualised volatility", "pct", 4, False, 252,
              ("kite",), "stdev of daily log returns x sqrt(252)"),
        _spec("risk.beta_1y", "Beta", "x", 4, None, 252, ("kite",), "vs NIFTY 50, 1y daily"),
        _spec("risk.max_dd_3y", "Max drawdown (3y)", "pct", 4, False, 504),
        _spec("risk.downside_dev_1y", "Downside deviation", "pct", 4, False, 252),
        _spec("risk.ulcer_index_1y", "Ulcer index", "score", 4, False, 252,
              ("kite",), "Depth x duration of drawdowns"),
        _spec("vol.volume_multiple", "Volume vs 20d average", "x", 4, None, 21,
              ("kite",), "Latest volume / ADV20"),
        _spec("vol.obv_slope_3m", "On-balance-volume slope", "score", 4, True, 64),
        # liq.*
        _spec("liq.adv_20d_inr", "20-day avg traded value", "inr_cr", 4, True, 20,
              ("kite",), "Hard filter at ₹5cr"),
        _spec("liq.spread_bps_est", "Estimated spread", "ratio", 4, False, 20,
              ("kite",), "Intraday when available, else daily-range proxy"),
        _spec("liq.impact_cost_1l", "Impact cost, ₹1L order", "pct", 4, False, 20),
        _spec("liq.days_to_exit", "Days to exit position", "days", 2, False, 20,
              ("kite",), "position_value / (0.10 x ADV)"),
        # val.*
        _spec("val.pe_ttm", "P/E (TTM)", "x", 4, None, 0, ("kite", "fundamentals"),
              "Shown but never scored directly"),
        _spec("val.pe_pctl_5y", "P/E percentile (5y own history)", "pct", 2, False, 1260,
              ("kite", "fundamentals"), "Lower = cheaper vs own past"),
        _spec("val.pe_pctl_10y", "P/E percentile (10y)", "pct", 2, False, 2520),
        _spec("val.pe_pctl_sector", "P/E percentile vs sector", "pct", 2, False, 0),
        _spec("val.ev_ebitda_pctl_5y", "EV/EBITDA percentile", "pct", 2, False, 1260),
        _spec("val.pb_pctl_5y", "P/B percentile", "pct", 2, False, 1260),
        _spec("val.ev_sales_pctl_5y", "EV/Sales percentile", "pct", 2, False, 1260,
              ("kite", "fundamentals"), "For pre-profit names"),
        _spec("val.earnings_yield_spread", "Earnings yield - 10y G-sec", "pct", 4, True, 0,
              ("kite", "fundamentals", "gsec"),
              "The one absolute valuation measure worth keeping"),
        # fin.*
        _spec("fin.revenue_cagr_3y", "Revenue CAGR (3y)", "pct", 4, True, 0, ("fundamentals",)),
        _spec("fin.revenue_cagr_5y", "Revenue CAGR (5y)", "pct", 4, True, 0, ("fundamentals",)),
        _spec("fin.ebitda_margin_ttm", "EBITDA margin (TTM)", "pct", 4, True, 0, ("fundamentals",)),
        _spec("fin.ebitda_margin_trend_4q", "Margin trend (4 quarters)", "pct", 4, True, 0,
              ("fundamentals",), "Linear slope, pp per quarter"),
        _spec("fin.pat_cagr_3y", "PAT CAGR (3y)", "pct", 4, True, 0, ("fundamentals",)),
        _spec("fin.roce_ttm", "ROCE (TTM)", "pct", 4, True, 0, ("fundamentals",),
              "EBIT / (equity + debt - cash)"),
        _spec("fin.roce_median_5y", "ROCE median (5y)", "pct", 4, True, 0, ("fundamentals",),
              "Median beats mean here"),
        _spec("fin.roce_stability_5y", "ROCE stability", "score", 4, True, 0, ("fundamentals",),
              "1 - (stdev/median), clipped [0,1]"),
        _spec("fin.roe_ttm", "ROE (TTM)", "pct", 4, True, 0, ("fundamentals",)),
        _spec("fin.debt_to_equity", "Debt / equity", "x", 4, False, 0, ("fundamentals",)),
        _spec("fin.debt_to_equity_trend", "D/E trend (8q)", "x", 4, False, 0,
              ("fundamentals",), "Slope"),
        _spec("fin.interest_coverage", "Interest coverage", "x", 4, True, 0,
              ("fundamentals",), "EBIT / interest"),
        _spec("fin.ocf_to_ebitda_5y", "Cash conversion (5y)", "ratio", 4, True, 0,
              ("fundamentals",), "The most underrated metric here"),
        _spec("fin.fcf_yield", "FCF yield", "pct", 4, True, 0, ("fundamentals", "kite")),
        _spec("fin.reinvestment_rate", "Reinvestment rate", "pct", 4, None, 0,
              ("fundamentals",), "(capex - dep) / EBIT"),
        _spec("fin.working_capital_days", "Working capital cycle", "days", 2, False, 0,
              ("fundamentals",)),
        _spec("fin.wc_days_trend_4q", "WC cycle trend", "days", 2, False, 0,
              ("fundamentals",), "Rising = warning"),
        # earn.*
        _spec("earn.surprise_last", "Last quarter surprise", "pct", 4, True, 0,
              ("fundamentals",), "vs consensus if available, else vs 4q trend"),
        _spec("earn.surprise_streak", "Consecutive beats", "count", 0, True, 0, ("fundamentals",)),
        _spec("earn.revision_3m", "Estimate revision (3m)", "pct", 4, True, 0,
              ("estimates",), "Requires estimates source; may be null"),
        _spec("earn.days_since_result", "Days since last result", "days", 0, None, 0, ("filings",)),
        _spec("earn.days_to_next_result", "Days to next result", "days", 0, None, 0,
              ("filings",), "From filing calendar"),
        # gov.*
        _spec("gov.promoter_pct", "Promoter holding", "pct", 3, None, 0, ("shareholding",)),
        _spec("gov.pledge_pct", "Promoter pledge", "pct", 3, False, 0, ("shareholding",),
              "> 20% is a hard warning at any horizon"),
        _spec("gov.pledge_trend_4q", "Pledge trend", "pct", 4, False, 0, ("shareholding",)),
        _spec("gov.fii_pct", "FII holding", "pct", 3, None, 0, ("shareholding",)),
        _spec("gov.fii_trend_4q", "FII trend", "pct", 4, True, 0, ("shareholding",)),
        _spec("gov.dii_trend_4q", "DII trend", "pct", 4, True, 0, ("shareholding",)),
        _spec("gov.auditor_change_24m", "Auditor changed (24m)", "count", 0, False, 0,
              ("filings",), "Any value > 0 is a flag"),
        _spec("gov.related_party_ratio", "Related-party txn / revenue", "pct", 4, False, 0,
              ("fundamentals",)),
        _spec("gov.contingent_liab_ratio", "Contingent liabilities / networth", "pct", 4, False, 0,
              ("fundamentals",)),
        # sec.*
        _spec("sec.relative_momentum", "Sector RS vs NIFTY 500 (3m)", "pct", 4, True, 64),
        _spec("sec.valuation_pctl", "Sector valuation percentile", "pct", 2, False, 0),
        _spec("sec.breadth", "% of sector above 50-DMA", "pct", 2, True, 50),
        # evt.* / qual.*
        _spec("evt.days_to_catalyst", "Days to next known catalyst", "days", 0, None, 0,
              ("filings",), "Results, ex-date, listing, regulatory"),
        _spec("qual.event_density", "Material filings (90d)", "count", 0, None, 0,
              ("qual_facts",), "Derived from qual_facts"),
        _spec("qual.guidance_direction", "Guidance direction", "score", 0, True, 0,
              ("qual_facts",), "-1/0/+1 from extracted facts"),
        _spec("qual.negative_fact_count", "Negative material facts (180d)", "count", 0, False, 0,
              ("qual_facts",)),
        # cost.*
        _spec("cost.hurdle_pct", "Break-even hurdle after costs & tax", "pct", 4, False, 0,
              ("config",)),
        _spec("cost.slippage_est_pct", "Estimated slippage", "pct", 4, False, 20),
        _spec("cost.round_trip_inr", "Round-trip cost", "inr", 2, False, 0, ("config",)),
        # meta.*
        _spec("meta.coverage", "Metric coverage", "pct", 2, True, 0, ("derived",),
              "Fraction computable"),
        _spec("meta.n_analogues", "Historical analogues used for band", "count", 0, True, 0,
              ("derived",)),
        _spec("meta.data_as_of", "Data current as of", "date", 0, None, 0, ("derived",)),
        _spec("meta.oldest_input_age", "Oldest input age", "days", 0, False, 0, ("derived",),
              "The honest staleness number"),
    ]
)
