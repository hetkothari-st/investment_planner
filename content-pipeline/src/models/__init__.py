from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from src.models.account import Account, SlotStat  # noqa: E402
from src.models.asset import Asset  # noqa: E402
from src.models.content import FormatSkeleton, Post, PostInsight, RenderJob, ScriptDraft  # noqa: E402
from src.models.trend import Trend, TrendSignal  # noqa: E402

__all__ = [
    "Base",
    "Account",
    "SlotStat",
    "Asset",
    "FormatSkeleton",
    "ScriptDraft",
    "RenderJob",
    "Post",
    "PostInsight",
    "Trend",
    "TrendSignal",
]
