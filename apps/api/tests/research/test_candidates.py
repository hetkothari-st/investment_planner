"""M5 acceptance: deterministic candidate set, ordered bands, falsifier
presence, cost-hurdle rejection, correlation prune."""

import dataclasses
import json
import math

from corpus.research.bands import Band, scenario_band
from corpus.research.candidates import (
    RejectionLog,
    generate_falsifiers,
    hurdle_pct,
    select_candidates,
)
from corpus.research.scoring import composite_scores

ISINS = [f"INE00{i}TEST" for i in range(6)]


def synthetic_universe():
    """Six symbols with deterministic sinusoid-ish price paths, two of them
    near-clones (for the correlation prune), one illiquid, one stale."""
    closes: dict[str, list[float]] = {}
    for k, isin in enumerate(ISINS):
        series = []
        for t in range(600):
            trend = 1 + (k + 1) * 0.0004
            wave = 1 + 0.03 * math.sin(t / (7 + k))
            series.append(100 * (trend**t) * wave)
        closes[isin] = series
    closes[ISINS[1]] = [c * 1.001 for c in closes[ISINS[0]]]  # clone of 0
    return closes


def build_inputs():
    closes = synthetic_universe()
    metric_values = {
        "mom.rs_3m": {i: 5.0 + k for k, i in enumerate(ISINS)},
        "mom.rs_1m": {i: 2.0 + k for k, i in enumerate(ISINS)},
        "vol.volume_multiple": {i: 1.0 + 0.2 * k for k, i in enumerate(ISINS)},
        "evt.days_to_catalyst": {i: 30.0 - k for k, i in enumerate(ISINS)},
        "liq.adv_20d_inr": {i: 20.0 for i in ISINS},
        "tech.dist_from_52w_high": {i: -5.0 - k for k, i in enumerate(ISINS)},
        "qual.event_density": {i: float(k) for k, i in enumerate(ISINS)},
        "risk.beta_1y": {i: 1.0 for i in ISINS},
        "gov.pledge_pct": {i: 4.0 for i in ISINS},
        "fin.ebitda_margin_ttm": {i: 18.0 for i in ISINS},
    }
    sectors = {i: ("FIN" if k < 3 else "IT") for k, i in enumerate(ISINS)}
    scores = composite_scores("SHORT", metric_values, sectors)
    bands = {}
    for isin in ISINS:
        band = scenario_band(
            [(-1) ** t * (3 + t % 17) + 6 for t in range(120)], []
        )
        bands[isin] = band
    prices = {i: closes[i][-1] for i in ISINS}
    adv = {i: (2.0 if i == ISINS[5] else 20.0) for i in ISINS}  # 5 is illiquid
    slippage = {i: 0.05 for i in ISINS}
    fresh = {i: (i != ISINS[4]) for i in ISINS}  # 4 is stale
    metrics_by_isin = {
        i: {f: v.get(i) for f, v in metric_values.items()} for i in ISINS
    }
    return scores, bands, prices, adv, slippage, metrics_by_isin, closes, fresh


def run_once():
    scores, bands, prices, adv, slip, by_isin, closes, fresh = build_inputs()
    return select_candidates(
        "SHORT", scores, bands, prices, adv, slip, by_isin, closes, fresh,
        log=RejectionLog(),
    )


def test_candidate_set_reproducible_byte_for_byte():
    """The M5 acceptance: two runs, identical serialised output."""
    a, log_a, _ = run_once()
    b, log_b, _ = run_once()
    dump = lambda cs: json.dumps(  # noqa: E731
        [dataclasses.asdict(c) for c in cs], sort_keys=True, default=str
    )
    assert dump(a) == dump(b)
    assert log_a.entries == log_b.entries
    assert a, "fixture should produce at least one candidate"


def test_bands_ordered_and_falsifiers_present():
    candidates, _, _ = run_once()
    for c in candidates:
        assert c.band.bear_pct < c.band.base_pct < c.band.bull_pct
        assert len(c.falsifiers) >= 1
        assert any(f.field_id == "price.close" for f in c.falsifiers)


def test_liquidity_stale_and_correlation_rejections_logged():
    candidates, log, _ = run_once()
    kept = {c.isin for c in candidates}
    assert ISINS[5] not in kept  # illiquid
    assert ISINS[4] not in kept  # stale
    joined = "\n".join(log.entries)
    assert "[liquidity]" in joined
    assert "[freshness]" in joined
    # the clone pair: at most one of ISINS[0]/ISINS[1] survives
    assert not ({ISINS[0], ISINS[1]} <= kept)
    assert "[correlation]" in joined


def test_cost_hurdle_rejects_thin_bands():
    """docs/05 required test: a 1-month band of +3% must be rejected under
    SHORT costs+tax."""
    from corpus.research.candidates import HURDLE_MARGIN_PCT

    h = hurdle_pct(price=200.0, qty=500, slippage_pct=0.05, horizon="SHORT")
    assert h + HURDLE_MARGIN_PCT["SHORT"] > 3.0  # +3% cannot clear the SHORT bar


def test_coverage_cap_blocks_candidate_set():
    """A stock with 55% coverage must never reach the candidate set."""
    scores, bands, prices, adv, slip, by_isin, closes, fresh = build_inputs()
    poor = [dataclasses.replace(s, coverage=0.55) for s in scores]
    candidates, log, _ = select_candidates(
        "SHORT", poor, bands, prices, adv, slip, by_isin, closes, fresh
    )
    assert candidates == []
    assert "[coverage]" in "\n".join(log.entries)


def test_price_falsifier_binds_to_bear_level():
    band = Band(bear_pct=-18.0, base_pct=8.0, bull_pct=22.0, n_analogues=100,
                conditioned=False)
    falsifiers = generate_falsifiers("MID", {"fin.ebitda_margin_ttm": 17.0}, band, 500.0)
    price_f = next(f for f in falsifiers if f.field_id == "price.close")
    assert price_f.threshold == 410.0  # 500 x (1 - 18%)
    margin_f = next(f for f in falsifiers if f.field_id == "fin.ebitda_margin_ttm")
    assert margin_f.threshold == 15.0
