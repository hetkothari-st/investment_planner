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
    true,
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
    # allocation preferences (docs/04 gate inputs). LOW is the conservative
    # default; max_lock_in_months None = no constraint stated.
    self_rated_knowledge: Mapped[str | None] = mapped_column(
        Text, server_default="LOW"
    )
    max_lock_in_months: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="single_user"),
        CheckConstraint(
            "job_stability IN ('LOW','MEDIUM','HIGH')", name="job_stability_valid"
        ),
        CheckConstraint(
            "self_rated_knowledge IN ('LOW','MEDIUM','HIGH')",
            name="self_rated_knowledge_valid",
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


# --- M4: recommendations, falsifiers, simulation, calibration — docs/02 ---


class Recommendation(Base):
    """IMMUTABLE once written. A Postgres trigger (migration 0003) rejects
    UPDATE on every column except status. The snapshot is the scientific
    record; edit nothing, ever."""

    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    isin: Mapped[str] = mapped_column(Text, nullable=False)
    tradingsymbol: Mapped[str | None] = mapped_column(Text)
    instrument_token: Mapped[int | None] = mapped_column(BigInteger)
    horizon: Mapped[str] = mapped_column(Text, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now()
    )
    expires_on: Mapped[date] = mapped_column(Date, nullable=False)
    ref_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    band_bear_pct: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    band_base_pct: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    band_bull_pct: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    conviction: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_size_inr: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    score_snapshot: Mapped[dict] = mapped_column(JsonB, nullable=False)
    weights_version: Mapped[str] = mapped_column(Text, nullable=False)
    report_md: Mapped[str] = mapped_column(Text, nullable=False)
    net_of_costs_hurdle_pct: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="LIVE")

    __table_args__ = (
        CheckConstraint("horizon IN ('SHORT','MID','LONG')", name="horizon_valid"),
        CheckConstraint(
            "conviction IN ('LOW','MODERATE','HIGH')", name="conviction_valid"
        ),
        CheckConstraint(
            "status IN ('LIVE','EXPIRED','INVALIDATED')", name="rec_status_valid"
        ),
        CheckConstraint(
            "band_bear_pct < band_base_pct AND band_base_pct < band_bull_pct",
            name="band_ordered",
        ),
    )


class Falsifier(Base):
    __tablename__ = "falsifiers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recommendations.id"), nullable=False
    )
    field_id: Mapped[str] = mapped_column(Text, nullable=False)
    operator: Mapped[str] = mapped_column(Text, nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    human_text: Mapped[str] = mapped_column(Text, nullable=False)
    breached_at: Mapped[datetime | None] = mapped_column(TZDateTime)

    __table_args__ = (
        CheckConstraint(
            "operator IN ('LT','LTE','GT','GTE','CROSSES_BELOW','CROSSES_ABOVE')",
            name="operator_valid",
        ),
    )


class SimPosition(Base):
    __tablename__ = "sim_positions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recommendations.id"), nullable=False
    )
    isin: Mapped[str] = mapped_column(Text, nullable=False)
    instrument_token: Mapped[int | None] = mapped_column(BigInteger)
    opened_on: Mapped[date] = mapped_column(Date, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    entry_costs_inr: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    thesis_snapshot_md: Mapped[str] = mapped_column(Text, nullable=False)
    closed_on: Mapped[date | None] = mapped_column(Date)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    exit_costs_inr: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    close_reason: Mapped[str | None] = mapped_column(Text)
    journal_note: Mapped[str | None] = mapped_column(Text)  # "Why now?"
    # set by a falsifier breach (docs/05): flagged, never auto-closed —
    # the close is the user's decision and that decision is scored later
    flagged_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    flag_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "close_reason IN ('MANUAL','FALSIFIER','EXPIRY','THESIS_CHANGED')",
            name="close_reason_valid",
        ),
    )


class SimMark(Base):
    __tablename__ = "sim_marks"

    position_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sim_positions.id"), primary_key=True
    )
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    close_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    mtm_inr: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    unrealised_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    drawdown_from_peak_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)


class CalibrationResult(Base):
    __tablename__ = "calibration_results"

    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recommendations.id"), primary_key=True
    )
    scored_on: Mapped[date] = mapped_column(Date, nullable=False)
    actual_return_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    actual_net_return_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    index_return_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    in_band: Mapped[bool] = mapped_column(Boolean, nullable=False)
    direction_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    brier: Mapped[Decimal | None] = mapped_column(Numeric(8, 5))
    band_error_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    calibration_version: Mapped[str] = mapped_column(Text, nullable=False)


# --- M5: fundamentals sources + the deterministic spine — docs/02 ---


class FundamentalsPeriod(Base):
    __tablename__ = "fundamentals_period"

    isin: Mapped[str] = mapped_column(Text, primary_key=True)
    period_end: Mapped[date] = mapped_column(Date, primary_key=True)
    period_type: Mapped[str] = mapped_column(Text, primary_key=True)  # Q | H | FY
    consolidated: Mapped[bool] = mapped_column(Boolean, primary_key=True, default=True)
    line_item: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    unit: Mapped[str] = mapped_column(Text, nullable=False, server_default="INR_CR")
    source: Mapped[str] = mapped_column(Text, nullable=False)
    as_of: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)

    __table_args__ = (
        CheckConstraint("period_type IN ('Q','H','FY')", name="period_type_valid"),
    )


class Filing(Base):
    __tablename__ = "filings"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    isin: Mapped[str] = mapped_column(Text, nullable=False)
    filed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    headline: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    ingested_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "category IN ('RESULTS','ANNOUNCEMENT','PLEDGE','SHP','CONCALL','AR')",
            name="category_valid",
        ),
    )


class Shareholding(Base):
    __tablename__ = "shareholding"

    isin: Mapped[str] = mapped_column(Text, primary_key=True)
    period_end: Mapped[date] = mapped_column(Date, primary_key=True)
    promoter_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    promoter_pledged_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    fii_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    dii_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    public_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    source: Mapped[str] = mapped_column(Text, nullable=False)


class MetricValueRow(Base):
    __tablename__ = "metric_values"

    isin: Mapped[str] = mapped_column(Text, primary_key=True)
    field_id: Mapped[str] = mapped_column(Text, primary_key=True)
    as_of: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    inputs_hash: Mapped[str] = mapped_column(Text, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now()
    )


class MetricGap(Base):
    __tablename__ = "metric_gaps"

    isin: Mapped[str] = mapped_column(Text, primary_key=True)
    field_id: Mapped[str] = mapped_column(Text, primary_key=True)
    as_of: Mapped[date] = mapped_column(Date, primary_key=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "reason IN ('INSUFFICIENT_HISTORY','SOURCE_STALE','NOT_APPLICABLE')",
            name="reason_valid",
        ),
    )


# --- M6: qualitative facts + the failure log — docs/02 ---


class QualFact(Base):
    __tablename__ = "qual_facts"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    isin: Mapped[str] = mapped_column(Text, nullable=False)
    filing_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("filings.id"))
    fact_type: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str | None] = mapped_column(Text)
    magnitude_band: Mapped[str | None] = mapped_column(Text)
    horizon_relevance: Mapped[dict | None] = mapped_column(JsonB)  # list serialised
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_span: Mapped[str | None] = mapped_column(Text)
    extracted_by: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "direction IN ('POSITIVE','NEGATIVE','NEUTRAL')", name="direction_valid"
        ),
    )


class CascadeGap(Base):
    __tablename__ = "cascade_gap"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    isin: Mapped[str | None] = mapped_column(Text)
    horizon: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    raw_output: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now()
    )


class Alert(Base):
    """Thesis-breakage alerts (docs/05): a stock down 8% with an intact
    thesis is noise; a stock flat with a broken thesis is urgent. One alert
    per breached falsifier, ever — the unique constraint is the idempotency."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False, default="FALSIFIER_BREACH")
    falsifier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("falsifiers.id"), nullable=False, unique=True
    )
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recommendations.id"), nullable=False
    )
    isin: Mapped[str] = mapped_column(Text, nullable=False)
    tradingsymbol: Mapped[str | None] = mapped_column(Text)
    horizon: Mapped[str] = mapped_column(Text, nullable=False)
    field_id: Mapped[str] = mapped_column(Text, nullable=False)
    operator: Mapped[str] = mapped_column(Text, nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    observed_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    observed_as_of: Mapped[date] = mapped_column(Date, nullable=False)
    # the original thesis line this breach contradicts, quoted verbatim from
    # the frozen report_md; thesis_line_found=False marks the honest fallback
    # (the falsifier text itself) when the frozen thesis never contained it
    thesis_line: Mapped[str] = mapped_column(Text, nullable=False)
    thesis_line_found: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=true()
    )
    raised_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now()
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(TZDateTime)
