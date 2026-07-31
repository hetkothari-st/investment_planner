"""Data-spine (M1) and user-state (M3) tables. Schema follows docs/02-DATA-LAYER.md."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from corpus.db.base import Base

# JSONB on Postgres, plain JSON elsewhere (tests run on SQLite).
JsonB = JSONB().with_variant(Text(), "sqlite")
# SQLite only autoincrements INTEGER primary keys, not BIGINT.
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")
TZDateTime = DateTime(timezone=True)


class Instrument(Base):
    __tablename__ = "instruments"

    instrument_token: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tradingsymbol: Mapped[str] = mapped_column(Text, nullable=False)
    exchange: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    isin: Mapped[str | None] = mapped_column(Text)
    segment: Mapped[str | None] = mapped_column(Text)
    lot_size: Mapped[int | None] = mapped_column(Integer)
    tick_size: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    expiry: Mapped[date | None] = mapped_column(Date)
    instrument_type: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("tradingsymbol", "exchange"),)


class Company(Base):
    __tablename__ = "companies"

    isin: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    sector: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(Text)
    mcap_band: Mapped[str | None] = mapped_column(Text)
    incorporated: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "mcap_band IN ('LARGE','MID','SMALL','MICRO')", name="mcap_band_valid"
        ),
    )


class UniverseMembership(Base):
    __tablename__ = "universe_membership"

    isin: Mapped[str] = mapped_column(
        Text, ForeignKey("companies.isin"), primary_key=True
    )
    index_name: Mapped[str] = mapped_column(Text, primary_key=True)  # 'NIFTY500', 'PINNED'
    from_date: Mapped[date] = mapped_column(Date, primary_key=True)
    to_date: Mapped[date | None] = mapped_column(Date)  # NULL = current


class TradingDay(Base):
    __tablename__ = "trading_calendar"

    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    exchange: Mapped[str] = mapped_column(Text, nullable=False, server_default="NSE")
    is_trading_day: Mapped[bool] = mapped_column(Boolean, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)


class OhlcvDaily(Base):
    __tablename__ = "ohlcv_daily"

    instrument_token: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    adj_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="kite")
    ingested_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now()
    )


class CorporateAction(Base):
    __tablename__ = "corporate_actions"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    isin: Mapped[str] = mapped_column(Text, nullable=False)
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    ratio_from: Mapped[Decimal | None] = mapped_column(Numeric)
    ratio_to: Mapped[Decimal | None] = mapped_column(Numeric)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    source: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("isin", "ex_date", "action_type"),
        CheckConstraint(
            "action_type IN ('SPLIT','BONUS','DIVIDEND','RIGHTS','MERGER')",
            name="action_type_valid",
        ),
    )


class IngestRun(Base):
    __tablename__ = "ingest_run"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    job: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="RUNNING")
    rows_written: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    errors: Mapped[dict | None] = mapped_column(JsonB)

    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING','OK','PARTIAL','FAILED')", name="status_valid"
        ),
    )


# --- M3: user state — docs/02 "User state" + docs/03 ---


class Profile(Base):
    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    display_name: Mapped[str | None] = mapped_column(Text)
    monthly_inflow: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    fixed_outflow: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    variable_outflow: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    liquid_balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    existing_investments: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    dependants: Mapped[int] = mapped_column(Integer, server_default="0")
    job_stability: Mapped[str | None] = mapped_column(Text)
    income_variability: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    temperament_choice: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="single_user"),
        CheckConstraint(
            "job_stability IN ('LOW','MEDIUM','HIGH')", name="job_stability_valid"
        ),
    )


class Debt(Base):
    __tablename__ = "debts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    principal_outstanding: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    annual_rate_pct: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    min_emi: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    tax_deductible: Mapped[bool] = mapped_column(Boolean, server_default="false")


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    priority: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("priority IN ('MUST','SHOULD','WANT')", name="priority_valid"),
    )


class PlanVersion(Base):
    __tablename__ = "plan_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now()
    )
    profile_snapshot: Mapped[dict] = mapped_column(JsonB, nullable=False)
    plan_result: Mapped[dict] = mapped_column(JsonB, nullable=False)
    rationale_md: Mapped[str] = mapped_column(Text, nullable=False)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
