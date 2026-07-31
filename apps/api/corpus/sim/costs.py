"""Round-trip cost model for NSE equity delivery — deterministic, versioned.

Cost and tax are modelled, not mentioned (docs/00 commitment 3). Every figure
comes from config/costs.v1.yaml; the golden test reconciles a hand-computed
contract note to the paise.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache

import yaml
from pydantic import BaseModel

from corpus.planner.assumptions import CONFIG_DIR

PAISE = Decimal("0.01")


class CostRates(BaseModel):
    version: str
    brokerage_buy_inr: Decimal
    brokerage_sell_inr: Decimal
    stt_buy_pct: Decimal
    stt_sell_pct: Decimal
    exchange_txn_pct: Decimal
    sebi_pct: Decimal
    stamp_buy_pct: Decimal
    gst_pct: Decimal
    dp_charge_sell_inr: Decimal
    slippage_floor_pct: Decimal


@lru_cache
def load_cost_rates(version: str = "v1") -> CostRates:
    return CostRates.model_validate(
        yaml.safe_load((CONFIG_DIR / f"costs.{version}.yaml").read_text())
    )


@dataclass(frozen=True)
class CostBreakdown:
    turnover_inr: Decimal
    brokerage: Decimal
    stt: Decimal
    exchange: Decimal
    sebi: Decimal
    stamp: Decimal
    gst: Decimal
    dp_charge: Decimal

    @property
    def total(self) -> Decimal:
        return (
            self.brokerage + self.stt + self.exchange + self.sebi
            + self.stamp + self.gst + self.dp_charge
        ).quantize(PAISE, rounding=ROUND_HALF_UP)


def _pct(value: Decimal, pct: Decimal) -> Decimal:
    return value * pct / 100


def buy_costs(price: Decimal, qty: int, rates: CostRates | None = None) -> CostBreakdown:
    r = rates or load_cost_rates()
    turnover = price * qty
    brokerage = r.brokerage_buy_inr
    exchange = _pct(turnover, r.exchange_txn_pct)
    sebi = _pct(turnover, r.sebi_pct)
    return CostBreakdown(
        turnover_inr=turnover,
        brokerage=brokerage,
        stt=_pct(turnover, r.stt_buy_pct),
        exchange=exchange,
        sebi=sebi,
        stamp=_pct(turnover, r.stamp_buy_pct),
        gst=_pct(brokerage + exchange + sebi, r.gst_pct),
        dp_charge=Decimal(0),
    )


def sell_costs(price: Decimal, qty: int, rates: CostRates | None = None) -> CostBreakdown:
    r = rates or load_cost_rates()
    turnover = price * qty
    brokerage = r.brokerage_sell_inr
    exchange = _pct(turnover, r.exchange_txn_pct)
    sebi = _pct(turnover, r.sebi_pct)
    return CostBreakdown(
        turnover_inr=turnover,
        brokerage=brokerage,
        stt=_pct(turnover, r.stt_sell_pct),
        exchange=exchange,
        sebi=sebi,
        stamp=Decimal(0),
        gst=_pct(brokerage + exchange + sebi, r.gst_pct),
        dp_charge=r.dp_charge_sell_inr,
    )


def slipped_price(close: Decimal, side: str, rates: CostRates | None = None) -> Decimal:
    """Entry pays up, exit gives up, by the slippage floor. The fuller
    spread/ADV estimate arrives with the liquidity metrics in M5."""
    r = rates or load_cost_rates()
    factor = 1 + r.slippage_floor_pct / 100 * (1 if side == "BUY" else -1)
    return (close * factor).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
