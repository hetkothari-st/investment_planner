from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class TrendSignal(Base):
    __tablename__ = "trend_signal"
    __table_args__ = (
        UniqueConstraint("source", "external_id", "observed_at", name="uq_signal"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_raw: Mapped[str] = mapped_column(Text, nullable=False)
    topic_norm: Mapped[str] = mapped_column(Text, nullable=False)
    niche: Mapped[str | None] = mapped_column(Text)
    metric_value: Mapped[float | None] = mapped_column(Numeric)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False)


class Trend(Base):
    __tablename__ = "trend"
    __table_args__ = (UniqueConstraint("topic_norm", "niche", name="uq_trend"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    topic_norm: Mapped[str] = mapped_column(Text, nullable=False)
    topic_display: Mapped[str] = mapped_column(Text, nullable=False)
    niche: Mapped[str] = mapped_column(Text, nullable=False)
    velocity_6h: Mapped[float] = mapped_column(Numeric, nullable=False, server_default="0")
    velocity_24h: Mapped[float] = mapped_column(Numeric, nullable=False, server_default="0")
    breadth: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    intensity: Mapped[float] = mapped_column(Numeric, nullable=False, server_default="0")
    phase: Mapped[str] = mapped_column(Text, nullable=False, server_default="emerging")
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
