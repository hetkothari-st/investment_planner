"""The nightly candidate flow — docs/05. Deterministic end to end.

universe -> liquidity filter -> freshness filter -> coverage filter ->
composite scoring -> cost-hurdle rejection -> top N -> correlation prune ->
falsifier generation. The SHORT engine is biased toward emitting nothing;
"no candidates today" is a successful result.

Every step logs what it dropped: the rejection log is genuinely informative.
"""

from dataclasses import dataclass, field

from corpus.research.bands import Band
from corpus.research.scoring import CompositeScore, conviction
from corpus.sim.costs import buy_costs, load_cost_rates, sell_costs

TOP_N = 8
FINAL_N = 5
MIN_ADV_CR = 5.0
MIN_COVERAGE = 0.60
CORRELATION_WARN = 0.6
# Base case must clear the hurdle by this much. SHORT is deliberately brutal:
# the correct output most days is "no short-horizon candidates today".
HURDLE_MARGIN_PCT = {"SHORT": 3.0, "MID": 2.0, "LONG": 2.0}

HORIZON_DAYS = {"SHORT": 42, "MID": 252, "LONG": 1008}
HORIZON_TAX = {"SHORT": 0.20, "MID": 0.125, "LONG": 0.125}


@dataclass(frozen=True)
class FalsifierSpec:
    field_id: str
    operator: str
    threshold: float
    human_text: str


@dataclass(frozen=True)
class Candidate:
    isin: str
    horizon: str
    composite_pctl: float
    coverage: float
    conviction: str
    band: Band
    hurdle_pct: float
    falsifiers: tuple[FalsifierSpec, ...]
    weights_version: str
    metric_pctls: dict[str, float]


@dataclass
class RejectionLog:
    entries: list[str] = field(default_factory=list)

    def add(self, isin: str, stage: str, detail: str) -> None:
        self.entries.append(f"{isin} [{stage}] {detail}")


def hurdle_pct(
    price: float, qty: int, slippage_pct: float, horizon: str
) -> float:
    """Break-even gross move: round-trip statutory costs + slippage, grossed
    up for the horizon's tax on the gain (docs/05)."""
    rates = load_cost_rates()
    from decimal import Decimal

    p = Decimal(str(price))
    entry = float(buy_costs(p, qty, rates).total)
    exit_ = float(sell_costs(p, qty, rates).total)
    slip = price * qty * (slippage_pct / 100) * 2  # both legs
    gross_needed = (entry + exit_ + slip) / (price * qty) * 100
    return gross_needed / (1 - HORIZON_TAX[horizon])


def generate_falsifiers(
    horizon: str,
    metrics: dict[str, float | None],
    band: Band,
    price: float,
) -> tuple[FalsifierSpec, ...]:
    """Templates bound to the horizon's dominant metrics — docs/05. The price
    falsifier always exists, so no recommendation can emit without one."""
    out: list[FalsifierSpec] = []
    rs3 = metrics.get("mom.rs_3m")
    if horizon == "SHORT" and rs3 is not None and rs3 > 0:
        out.append(
            FalsifierSpec(
                "mom.rs_3m", "LT", round(rs3 * 0.5, 4),
                "3-month relative strength halves from entry",
            )
        )
    pledge = metrics.get("gov.pledge_pct")
    if pledge is not None:
        out.append(
            FalsifierSpec(
                "gov.pledge_pct", "GT", round(pledge + 5.0, 4),
                "Promoter pledge rises 5pp above entry level",
            )
        )
    margin = metrics.get("fin.ebitda_margin_ttm")
    if horizon in ("MID", "LONG") and margin is not None:
        out.append(
            FalsifierSpec(
                "fin.ebitda_margin_ttm", "LT", round(margin - 2.0, 4),
                "TTM EBITDA margin falls 2pp from entry",
            )
        )
    out.append(
        FalsifierSpec(
            "price.close", "LT", round(price * (1 + band.bear_pct / 100), 4),
            "Price breaches the bear-case level",
        )
    )
    return tuple(out)


def pairwise_correlation(a: list[float], b: list[float]) -> float | None:
    n = min(len(a), len(b))
    if n < 30:
        return None
    ra = [(y / x - 1) for x, y in zip(a[-n:], a[-n + 1 :], strict=False)]
    rb = [(y / x - 1) for x, y in zip(b[-n:], b[-n + 1 :], strict=False)]
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb, strict=True))
    va = sum((x - ma) ** 2 for x in ra)
    vb = sum((y - mb) ** 2 for y in rb)
    if va == 0 or vb == 0:
        return None
    return cov / (va * vb) ** 0.5


def correlation_prune(
    ranked: list[str],
    closes: dict[str, list[float]],
    keep: int = FINAL_N,
    max_corr: float = 0.85,
) -> tuple[list[str], list[str]]:
    """Greedy: walk the ranking, drop any name correlated > max_corr with an
    already-kept name. Returns (kept, dropped_notes)."""
    kept: list[str] = []
    notes: list[str] = []
    for isin in ranked:
        if len(kept) >= keep:
            break
        clash = None
        for held in kept:
            corr = pairwise_correlation(closes.get(isin, []), closes.get(held, []))
            if corr is not None and corr > max_corr:
                clash = (held, corr)
                break
        if clash:
            notes.append(f"{isin} dropped: {clash[1]:.2f} correlation with {clash[0]}")
        else:
            kept.append(isin)
    return kept, notes


def mean_pairwise_correlation(
    isins: list[str], closes: dict[str, list[float]]
) -> float | None:
    pairs = [
        pairwise_correlation(closes.get(a, []), closes.get(b, []))
        for i, a in enumerate(isins)
        for b in isins[i + 1 :]
    ]
    vals = [p for p in pairs if p is not None]
    return sum(vals) / len(vals) if vals else None


def select_candidates(
    horizon: str,
    scores: list[CompositeScore],
    bands: dict[str, Band],
    prices: dict[str, float],
    adv_cr: dict[str, float | None],
    slippage: dict[str, float],
    metrics_by_isin: dict[str, dict[str, float | None]],
    closes: dict[str, list[float]],
    data_fresh: dict[str, bool],
    log: RejectionLog | None = None,
) -> tuple[list[Candidate], RejectionLog, list[str]]:
    """Steps 1-7 of the candidate flow. Deterministic: ties break on isin."""
    log = log or RejectionLog()

    eligible: list[CompositeScore] = []
    for s in sorted(scores, key=lambda s: (-s.composite_pctl, s.isin)):
        adv = adv_cr.get(s.isin)
        if adv is None or adv < MIN_ADV_CR:
            log.add(s.isin, "liquidity", f"ADV {adv} cr below ₹{MIN_ADV_CR}cr")
            continue
        if not data_fresh.get(s.isin, False):
            log.add(s.isin, "freshness", "stale inputs; scoring refused")
            continue
        if s.coverage < MIN_COVERAGE:
            log.add(s.isin, "coverage", f"{s.coverage:.0%} of weighted metrics")
            continue
        if s.isin not in bands:
            log.add(s.isin, "band", "no honest band computable")
            continue
        eligible.append(s)

    survivors: list[CompositeScore] = []
    hurdles: dict[str, float] = {}
    for s in eligible:
        band = bands[s.isin]
        price = prices[s.isin]
        qty = max(1, int(100_000 / price))
        h = hurdle_pct(price, qty, slippage[s.isin], horizon)
        hurdles[s.isin] = h
        margin = HURDLE_MARGIN_PCT[horizon]
        if band.base_pct < h + margin:
            log.add(
                s.isin, "hurdle",
                f"base {band.base_pct}% under hurdle {h:.2f}% + {margin}% margin",
            )
            continue
        survivors.append(s)

    top = survivors[:TOP_N]
    kept_isins, corr_notes = correlation_prune([s.isin for s in top], closes)
    for note in corr_notes:
        log.add(note.split(" ")[0], "correlation", note)

    final = [s for s in top if s.isin in kept_isins]
    warnings: list[str] = []
    mean_corr = mean_pairwise_correlation(kept_isins, closes)
    if mean_corr is not None and mean_corr > CORRELATION_WARN:
        warnings.append(
            f"These {len(kept_isins)} names moved together "
            f"{mean_corr:.0%} of the time over the last year. "
            "This is one bet in several wrappers."
        )

    candidates = []
    for s in final:
        band = bands[s.isin]
        falsifiers = generate_falsifiers(
            horizon, metrics_by_isin.get(s.isin, {}), band, prices[s.isin]
        )
        assert falsifiers, f"{s.isin}: no falsifier generated — refusing to emit"
        candidates.append(
            Candidate(
                isin=s.isin,
                horizon=horizon,
                composite_pctl=round(s.composite_pctl, 4),
                coverage=round(s.coverage, 4),
                conviction=conviction(s.composite_pctl, s.coverage),
                band=band,
                hurdle_pct=round(hurdles[s.isin], 4),
                falsifiers=falsifiers,
                weights_version=s.weights_version,
                metric_pctls={k: round(v, 4) for k, v in sorted(s.metric_pctls.items())},
            )
        )
    return candidates, log, warnings
