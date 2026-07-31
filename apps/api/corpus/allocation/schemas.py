"""Allocation output shapes — docs/04-ALLOCATION-ENGINE.md.

Money follows the planner convention: Decimal rupees internally, integer
paise in JSON transport.
"""

from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

from corpus.planner.schemas import HorizonBucket, Money


class Knowledge(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AllocationPreferences(BaseModel):
    """The two allocation inputs the planner does not already hold.

    self_rated_knowledge defaults LOW: the conservative reading gates
    HIGH-knowledge vehicles out until the user claims otherwise.
    max_lock_in_months None means the user has stated no constraint;
    the lock-in gate then passes and the UI says so.
    """

    self_rated_knowledge: Knowledge = Knowledge.LOW
    max_lock_in_months: int | None = None


class AllocationLine(BaseModel):
    vehicle_id: str
    label: str
    bucket: HorizonBucket
    lumpsum_inr: Money
    monthly_inr: Money
    rationale: str


class VehicleScore(BaseModel):
    vehicle_id: str
    label: str
    suitability_pct: Decimal  # 0..100, 1dp
    components: dict[str, Decimal]  # fit_horizon/.../fit_effort, each 0..1
    net_expected_return_pct: Decimal
    volatility_annual_pct: Decimal
    liquidity_days: int
    lock_in_months: int
    effort: str
    knowledge_required: str
    allocated_lumpsum: Money
    allocated_monthly: Money


class GatedVehicle(BaseModel):
    vehicle_id: str
    label: str
    gate: str
    explanation: str
    # the ghost still needs a position in the scatter
    net_expected_return_pct: Decimal
    volatility_annual_pct: Decimal
    liquidity_days: int
    lock_in_months: int


class Allocation(BaseModel):
    plan_version_id: UUID | None
    horizon_months: int  # the horizon the ranked list is scored at
    lines: list[AllocationLine]
    ranked_vehicles: list[VehicleScore]
    gated_out: list[GatedVehicle]
    vehicles_version: str
    assumptions_version: str
    diversification_notes: list[str]
    preferences: AllocationPreferences
