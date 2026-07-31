"""Manual thesis entry — M4 seeds the ledger with the user's own picks.

The system starts grading you before it grades itself. Every rule that will
bind machine recommendations binds manual ones: a horizon, a scenario band
(bear < base < bull), and at least one machine-checkable falsifier. No
falsifier, no thesis.
"""

import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from corpus.db.models import Falsifier, Recommendation
from corpus.planner.schemas import Money


class FalsifierIn(BaseModel):
    field_id: str
    operator: str  # LT | LTE | GT | GTE | CROSSES_BELOW | CROSSES_ABOVE
    threshold: Decimal
    human_text: str


class ManualThesisIn(BaseModel):
    isin: str
    tradingsymbol: str | None = None
    instrument_token: int | None = None
    horizon: str  # SHORT | MID | LONG
    expires_on: date
    ref_price: Decimal
    band_bear_pct: Decimal
    band_base_pct: Decimal
    band_bull_pct: Decimal
    conviction: str  # LOW | MODERATE | HIGH
    suggested_size_inr: Money
    thesis_md: str = Field(min_length=10, description="Your reasoning, frozen at issue")
    falsifiers: list[FalsifierIn] = Field(min_length=1)

    @model_validator(mode="after")
    def bands_ordered(self):
        if not (self.band_bear_pct < self.band_base_pct < self.band_bull_pct):
            raise ValueError("bands must satisfy bear < base < bull")
        return self


async def create_manual_thesis(
    session: AsyncSession, body: ManualThesisIn, issued_on: date
) -> Recommendation:
    rec = Recommendation(
        id=uuid.uuid4(),
        issued_at=datetime.combine(issued_on, time(0, 0), tzinfo=UTC),
        isin=body.isin,
        tradingsymbol=body.tradingsymbol,
        instrument_token=body.instrument_token,
        horizon=body.horizon,
        expires_on=body.expires_on,
        ref_price=body.ref_price,
        band_bear_pct=body.band_bear_pct,
        band_base_pct=body.band_base_pct,
        band_bull_pct=body.band_bull_pct,
        conviction=body.conviction,
        suggested_size_inr=body.suggested_size_inr,
        score_snapshot=_snapshot(session, body),
        weights_version="manual",
        report_md=body.thesis_md,
        net_of_costs_hurdle_pct=Decimal(0),  # computed for machine theses from M5
        status="LIVE",
    )
    session.add(rec)
    # No relationship() is declared between the mappers, so flush explicitly:
    # the falsifier rows must see the recommendation row.
    await session.flush()
    for f in body.falsifiers:
        session.add(
            Falsifier(
                id=uuid.uuid4(),
                recommendation_id=rec.id,
                field_id=f.field_id,
                operator=f.operator,
                threshold=f.threshold,
                human_text=f.human_text,
            )
        )
    await session.commit()
    return rec


def _snapshot(session: AsyncSession, body: ManualThesisIn) -> dict | str:
    import json

    payload = {
        "source": "manual",
        "issued_inputs": body.model_dump(mode="json", exclude={"thesis_md"}),
    }
    return json.dumps(payload) if session.bind.dialect.name == "sqlite" else payload
