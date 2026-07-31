"""Versioned vehicle characteristics — docs/04-ALLOCATION-ENGINE.md.

Everything here is a declared assumption, not a measurement. The allocation
records which version produced it.
"""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

# repo_root/config — three levels up from corpus/allocation/
CONFIG_DIR = Path(__file__).resolve().parents[4] / "config"


class TaxSide(BaseModel):
    rate: Decimal
    threshold_months: int | None = None
    exemption_inr: Decimal | None = None


class Tax(BaseModel):
    short_term: TaxSide
    long_term: TaxSide


class Vehicle(BaseModel):
    id: str
    label: str
    enabled: bool = True
    disabled_reason: str | None = None
    expected_real_return_pct: Decimal
    volatility_annual_pct: Decimal
    max_historical_dd_pct: Decimal
    liquidity_days: int
    lock_in_months: int
    min_horizon_months: int
    natural_horizon_months: int
    cost_drag_pct: Decimal
    expense_ratio_pct: Decimal
    tax: Tax
    effort: str
    knowledge_required: str


class ScoringWeights(BaseModel):
    w_horizon: Decimal
    w_drawdown: Decimal
    w_liquidity: Decimal
    w_return: Decimal
    w_effort: Decimal
    return_norm_pct: Decimal


class Construction(BaseModel):
    max_vehicle_weight: Decimal
    index_floor: Decimal
    gold_ceiling: Decimal
    intl_ceiling: Decimal
    sip_round_inr: Decimal


class VehicleConfig(BaseModel):
    version: str
    scoring: ScoringWeights
    construction: Construction
    vehicles: list[Vehicle]

    def by_id(self, vehicle_id: str) -> Vehicle:
        return next(v for v in self.vehicles if v.id == vehicle_id)


@lru_cache
def load_vehicles(version: str = "v1") -> VehicleConfig:
    path = CONFIG_DIR / f"vehicles.{version}.yaml"
    return VehicleConfig.model_validate(yaml.safe_load(path.read_text()))
