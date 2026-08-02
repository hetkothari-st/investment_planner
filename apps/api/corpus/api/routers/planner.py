"""Planner routes. Thin: routers call services, services call the engine."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from corpus.db.models import Debt, Goal, Profile
from corpus.db.session import get_session
from corpus.planner.assumptions import load_assumptions
from corpus.planner.schemas import DebtIn, GoalIn, PlanResult, ProfileIn
from corpus.planner.service import (
    ProfileIncomplete,
    compute_and_persist,
    latest_plan,
    load_plan_input,
)
from corpus.planner.temperament import TOLERATED_DD_FRACTION, scenario_amounts

router = APIRouter(prefix="/planner", tags=["planner"])


class UserState(BaseModel):
    profile: ProfileIn | None
    debts: list[DebtIn]
    goals: list[GoalIn]


@router.get("/state")
async def get_state(session: AsyncSession = Depends(get_session)) -> UserState:
    profile = await session.get(Profile, 1)
    debts = (await session.execute(select(Debt))).scalars().all()
    goals = (await session.execute(select(Goal))).scalars().all()
    profile_out = None
    if profile is not None and profile.monthly_inflow is not None:
        state = await load_plan_input(session, datetime.now(UTC).date())
        return UserState(profile=state.profile, debts=state.debts, goals=state.goals)
    return UserState(
        profile=profile_out,
        debts=[DebtIn.model_validate(d, from_attributes=True) for d in debts],
        goals=[GoalIn.model_validate(g, from_attributes=True) for g in goals],
    )


@router.put("/profile")
async def put_profile(
    body: ProfileIn, session: AsyncSession = Depends(get_session)
) -> ProfileIn:
    profile = await session.get(Profile, 1)
    if profile is None:
        profile = Profile(id=1)
        session.add(profile)
    for field, value in body.model_dump().items():
        setattr(profile, field, value)
    await session.commit()
    return body


@router.put("/debts")
async def put_debts(
    body: list[DebtIn], session: AsyncSession = Depends(get_session)
) -> list[DebtIn]:
    await session.execute(delete(Debt))
    for d in body:
        session.add(Debt(id=uuid.uuid4(), **d.model_dump()))
    await session.commit()
    return body


@router.put("/goals")
async def put_goals(
    body: list[GoalIn], session: AsyncSession = Depends(get_session)
) -> list[GoalIn]:
    await session.execute(delete(Goal))
    for g in body:
        session.add(Goal(id=uuid.uuid4(), **g.model_dump()))
    await session.commit()
    return body


@router.post("/plan")
async def create_plan(session: AsyncSession = Depends(get_session)) -> PlanResult:
    try:
        return await compute_and_persist(session, datetime.now(UTC).date())
    except ProfileIncomplete as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/plan/latest")
async def get_latest_plan(session: AsyncSession = Depends(get_session)) -> PlanResult:
    result = await latest_plan(session)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No plan computed yet. Complete the profile and compute one.",
        )
    return result


class ScenarioOption(BaseModel):
    choice: str
    label: str
    tolerated_dd_fraction: str


class TemperamentScenario(BaseModel):
    before_inr: int  # paise? no — whole rupees for display
    after_inr: int
    options: list[ScenarioOption]


OPTION_LABELS = {
    "SELL_EVERYTHING": "Sell everything. I could not watch it fall further.",
    "SELL_SOME": "Sell some to stop the bleeding, keep the rest.",
    "HOLD": "Do nothing. This is what drawdowns look like.",
    "BUY_MORE": "Buy more. The plan priced this in.",
}


@router.get("/temperament-scenario")
async def temperament_scenario(
    session: AsyncSession = Depends(get_session),
) -> TemperamentScenario:
    """The scenario question, scaled to the user's actual corpus."""
    profile = await session.get(Profile, 1)
    corpus = (
        (profile.liquid_balance or 0) + (profile.existing_investments or 0)
        if profile
        else 0
    )
    a = load_assumptions()
    before, after = scenario_amounts(corpus, a.assumed_equity_max_dd)
    return TemperamentScenario(
        before_inr=int(before),
        after_inr=int(after),
        options=[
            ScenarioOption(
                choice=choice.value,
                label=OPTION_LABELS[choice.value],
                tolerated_dd_fraction=str(frac),
            )
            for choice, frac in TOLERATED_DD_FRACTION.items()
        ],
    )
