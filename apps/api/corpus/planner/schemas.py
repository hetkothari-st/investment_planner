"""Planner input/output shapes — docs/03-PLANNER-ENGINE.md.

Money is Decimal internally; the API layer serialises to integer paise.
"""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field, PlainSerializer

from corpus.planner.temperament import TemperamentChoice

# Money convention (CLAUDE.md): Decimal in Python, integer paise in JSON
# transport. An int in JSON is paise; strings/Decimals are rupees (internal
# callers and test fixtures).
Money = Annotated[
    Decimal,
    BeforeValidator(lambda v: Decimal(v) / 100 if isinstance(v, int) else v),
    PlainSerializer(
        lambda v: int((v * 100).to_integral_value(ROUND_HALF_UP)),
        return_type=int,
        when_used="json",  # python-mode dumps keep Decimal rupees
    ),
]


class JobStability(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class GoalPriority(StrEnum):
    MUST = "MUST"
    SHOULD = "SHOULD"
    WANT = "WANT"


class DebtIn(BaseModel):
    label: str
    principal_outstanding: Money
    annual_rate_pct: Decimal
    min_emi: Money = Decimal(0)
    tax_deductible: bool = False


class GoalIn(BaseModel):
    label: str
    target_amount: Money
    target_date: date
    priority: GoalPriority = GoalPriority.SHOULD


class ProfileIn(BaseModel):
    display_name: str | None = None
    monthly_inflow: Money
    fixed_outflow: Money
    variable_outflow: Money
    liquid_balance: Money
    existing_investments: Money = Decimal(0)
    dependants: int = 0
    job_stability: JobStability = JobStability.MEDIUM
    income_variability: Decimal = Decimal(0)  # stdev/mean of last 12 months
    temperament_choice: TemperamentChoice = TemperamentChoice.SELL_SOME


class PlanInput(BaseModel):
    profile: ProfileIn
    debts: list[DebtIn] = Field(default_factory=list)
    goals: list[GoalIn] = Field(default_factory=list)
    as_of: date


class GateStatus(StrEnum):
    PASSED = "PASSED"
    BLOCKED = "BLOCKED"
    INFO = "INFO"


class GateResult(BaseModel):
    gate: str  # G1..G6
    label: str
    status: GateStatus
    amount: Money  # rupees routed through/withheld by this gate; paise in JSON
    reason: str


class SensitivityRow(BaseModel):
    equity_real_return_pct: Decimal
    hurdle_pct: Decimal
    investable_monthly: Money
    note: str


class HorizonBucket(StrEnum):
    LIQUID_0_12 = "LIQUID_0_12"
    DEBT_12_36 = "DEBT_12_36"
    HYBRID_36_60 = "HYBRID_36_60"
    EQUITY_60_PLUS = "EQUITY_60_PLUS"


class PlanResult(BaseModel):
    version_id: UUID | None = None
    generated_at: datetime | None = None
    gates: list[GateResult]
    investable_monthly: Money
    investable_lumpsum: Money
    buffer_target: Money
    buffer_current: Money
    buffer_eta_months: int | None
    blocking_reasons: list[str]
    spending_recommendations: list[str]
    max_equity_fraction: Decimal
    horizon_buckets: dict[HorizonBucket, Money]
    assumptions_version: str
    sensitivity: list[SensitivityRow]
