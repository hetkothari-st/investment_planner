from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class FormatSkeleton(Base):
    __tablename__ = "format_skeleton"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    trend_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("trend.id", ondelete="CASCADE")
    )
    skeleton: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ScriptDraft(Base):
    __tablename__ = "script_draft"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("account.id"), nullable=False
    )
    trend_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trend.id"), nullable=False)
    skeleton_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("format_skeleton.id"), nullable=False
    )
    template_key: Mapped[str] = mapped_column(Text, nullable=False)
    beats: Mapped[dict] = mapped_column(JSONB, nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RenderJob(Base):
    __tablename__ = "render_job"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    script_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("script_draft.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    output_path: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Post(Base):
    __tablename__ = "post"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("account.id"), nullable=False
    )
    render_job_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("render_job.id"), nullable=False
    )
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    platform_id: Mapped[str | None] = mapped_column(Text)
    slot: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending_qc")
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    caption: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)


class PostInsight(Base):
    __tablename__ = "post_insight"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("post.id", ondelete="CASCADE"), nullable=False
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    impressions: Mapped[int | None] = mapped_column(BigInteger)
    reach: Mapped[int | None] = mapped_column(BigInteger)
    saves: Mapped[int | None] = mapped_column(BigInteger)
    shares: Mapped[int | None] = mapped_column(BigInteger)
    comments: Mapped[int | None] = mapped_column(BigInteger)
    likes: Mapped[int | None] = mapped_column(BigInteger)
    watch_pct: Mapped[float | None] = mapped_column(Numeric)
    reward: Mapped[float | None] = mapped_column(Numeric)
