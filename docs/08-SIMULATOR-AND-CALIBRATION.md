# 08 — Simulator & Calibration

Build this **before** the recommendation engine ships its first report, so that every
output the system has ever produced is scored. This ordering is the single most
consequential decision in the project.

## Simulator

### What it is
A paper position with full cost modelling and a **frozen thesis snapshot**.

### What it is not
A game. There is no leaderboard, no streak, no badge. It exists to test whether the
reasoning was sound, not to make losing feel fun.

### Opening a position

```python
def open_simulated(rec_id: UUID, amount_inr: Decimal) -> SimPosition:
    rec = get_recommendation(rec_id)          # immutable
    price = last_close(rec.isin)
    qty = int(amount_inr // price)
    costs = compute_entry_costs(price, qty)   # brokerage, STT, exchange, GST, stamp, slippage
    return SimPosition(
        recommendation_id=rec_id,
        qty=qty,
        entry_price=price + slippage_adjustment(price, qty),
        entry_costs_inr=costs,
        thesis_snapshot_md=rec.report_md,     # FROZEN. Never regenerated.
    )
```

**`thesis_snapshot_md` is copied, not referenced.** If you re-render the report later
from current data, you will unconsciously rewrite history and learn nothing. The frozen
copy is the entire scientific value of the feature.

### Daily marking (pipeline step 9)

For each open position, write a `sim_marks` row:

```
mtm_inr              = qty × close − qty × entry_price − entry_costs
unrealised_pct       = mtm_inr / (qty × entry_price)
drawdown_from_peak   = (close − running_peak) / running_peak
```

Also compute, for display:
- XIRR (positions may be opened at different times)
- vs NIFTY 500 over the identical holding window — **always shown alongside**. A +14%
  position during a +19% market is a failure and must read as one.
- days held, days to horizon expiry
- current portfolio heat across all open positions

### Closing
Manual close, falsifier-triggered prompt, or horizon expiry.
`close_reason` is recorded: `MANUAL | FALSIFIER | EXPIRY | THESIS_CHANGED`.

Closing prompts a one-field journal entry: *"Why now?"* Free text. When you later read
the calibration view, these entries are more instructive than the P&L.

## Calibration Ledger

The feature no commercial product will ever ship, because it publishes the system's
own failure rate.

### What gets scored

Every recommendation, on `expires_on`, regardless of whether it was simulated:

```python
class CalibrationResult:
    actual_return_pct: Decimal        # ref_price → close on expiry
    actual_net_return_pct: Decimal    # after modelled round-trip costs and tax
    in_band: bool                     # bear <= actual <= bull
    direction_correct: bool           # sign(actual) == sign(band_base)
    band_error_pct: Decimal           # |actual − band_base|
    brier: Decimal                    # on the direction call, using conviction as probability
```

Conviction → probability mapping for Brier scoring:
`LOW → 0.55`, `MODERATE → 0.65`, `HIGH → 0.78`.
These start as assumptions and get **recalibrated from observed data** after 50 scored
recommendations per horizon. Store the mapping with a version.

### The aggregate metrics

| Metric | Meaning | Target |
|---|---|---|
| **Band coverage** | % of outcomes inside bear–bull | ~60% (you set p20/p80) |
| **Direction hit rate** | by horizon, by conviction | > 50% or the horizon is noise |
| **Brier score** | calibration of confidence | < 0.25 |
| **Reliability curve** | predicted vs realised, bucketed | on the diagonal |
| **Net alpha** | vs NIFTY 500, same windows, after costs | the only one that matters |

**Band coverage above ~85% means your bands are too wide to be useful.**
Below ~40% means they're fantasy. Both are failures; show both directions.

### The honest verdict

The calibration page renders a plain-language verdict per horizon:

> **SHORT (1–3 months) — 41 scored calls**
> Direction correct 44% of the time. Net of costs, this horizon has produced −2.3%
> against a +6.1% index. **This system is not good at short-horizon calls.**
> Suggested action: stop acting on them, or reduce sizing to research-only.

Write these verdicts as templated deterministic text with thresholds, not LLM prose.
The system grading itself must not be able to spin.

### Minimum sample gating

Do not show a hit rate below 20 scored recommendations for a horizon. Show
`n scored / 20 needed` instead. Small-sample hit rates are actively misleading and
you will over-update on them.

### Weight-set comparison

Because every recommendation stores `weights_version`, the calibration view can compare:

```
weights.v1 — MID horizon — 63 calls — direction 61% — net alpha +3.2%
weights.v2 — MID horizon — 28 calls — direction 57% — net alpha +0.4%   [n too low]
```

This turns your scoring config into an experiment rather than a guess. Once you have
enough data, this is how the system actually improves — not by better prompts.

## The dashboard signature

The calibration state renders as the app's signature element: a machined **calibration
dial** with three needles (SHORT / MID / LONG), each pointing at measured direction
hit rate on an arc from 30% to 80%, with a 50% coin-flip mark engraved on the face.

When a horizon has insufficient data, its needle rests at a detent position marked
`UNCALIBRATED` and reads as inactive — not as zero.

See `docs/09-DESIGN-SYSTEM.md` for the full spec. This is the one place in the app
that spends real visual ambition, and it's justified because it's the product's thesis
made physical: an instrument that measures the instrument.

## Tests

- Open → mark 30 days → close: P&L reconciles to the paise against a hand-computed fixture.
- Costs: a round trip on a ₹50,000 position matches a manually computed brokerage sheet.
- Frozen snapshot: regenerating the report must not alter `thesis_snapshot_md`. Assert equality.
- Band coverage: with synthetic recommendations drawn from a known distribution, measured
  coverage must converge to the nominal 60%.
- Gating: with 19 scored calls, the UI must show the sample-count message, not a rate.
