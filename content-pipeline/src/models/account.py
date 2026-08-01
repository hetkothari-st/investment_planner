from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class Account(Base):
    __tablename__ = "account"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    niche: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    ig_user_id: Mapped[str | None] = mapped_column(Text)
    yt_channel_id: Mapped[str | None] = mapped_column(Text)
    posts_per_day: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SlotStat(Base):
    __tablename__ = "slot_stat"
    __table_args__ = (UniqueConstraint("account_id", "slot", "dow", name="uq_slot"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("account.id"), nullable=False
    )
    slot: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    dow: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    alpha: Mapped[float] = mapped_column(Numeric, nullable=False, server_default="1.0")
    beta: Mapped[float] = mapped_column(Numeric, nullable=False, server_default="1.0")
    n: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
