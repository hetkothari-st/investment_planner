"""Common Source protocol — docs/02-DATA-LAYER.md.

Every non-Kite source (filings, shareholding, announcements, ...) implements
this so any one can be swapped without touching downstream code.
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Protocol


class SourceStatus(StrEnum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"


@dataclass(frozen=True)
class SourceHealth:
    status: SourceStatus
    last_success_at: datetime | None
    detail: str | None = None


@dataclass(frozen=True)
class RawRecord:
    source: str
    entity: str  # symbol / isin the record belongs to
    as_of: date
    payload: dict[str, Any]


class Source(Protocol):
    name: str

    async def fetch(self, symbol: str, since: date) -> list[RawRecord]: ...

    def health(self) -> SourceHealth: ...
