"""MetricValue — the only shape a metric function may return.

A metric that cannot be computed returns value=None with a reason — never a
default, never an imputation. The caller persists; metric functions do not
touch the network or the database.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

GapReason = Literal["INSUFFICIENT_HISTORY", "SOURCE_STALE", "NOT_APPLICABLE"]


@dataclass(frozen=True)
class MetricValue:
    field_id: str
    value: Decimal | None
    unit: str
    as_of: date
    inputs_hash: str
    reason: GapReason | None = None

    def __post_init__(self):
        assert (self.value is None) != (self.reason is None), (
            f"{self.field_id}: exactly one of value/reason"
        )


def inputs_hash(payload: Any) -> str:
    """Stable hash of the raw inputs a metric consumed; enables cache
    invalidation and byte-for-byte reproducibility checks."""
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


def q(value: float | Decimal, precision: int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal(1).scaleb(-precision))
