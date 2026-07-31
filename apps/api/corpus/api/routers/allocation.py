"""Allocation routes. Deterministic: latest plan + profile + versioned
vehicle config in, allocation out. Nothing here waits on anything."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from corpus.allocation.engine import build_allocation
from corpus.allocation.schemas import Allocation, AllocationPreferences
from corpus.allocation.vehicles import load_vehicles
from corpus.db.models import Profile
from corpus.db.session import get_session
from corpus.planner.assumptions import load_assumptions
from corpus.planner.service import latest_plan
from corpus.planner.temperament import TemperamentChoice

router = APIRouter(prefix="/allocation", tags=["allocation"])


@router.get("")
async def get_allocation(session: AsyncSession = Depends(get_session)) -> Allocation:
    plan = await latest_plan(session)
    if plan is None:
        raise HTTPException(
            404, "No plan computed yet. Complete the profile and compute one."
        )
    if plan.blocking_reasons:
        raise HTTPException(
            409,
            "The plan is blocked; allocation stays locked: "
            + "; ".join(plan.blocking_reasons),
        )
    profile = await session.get(Profile, 1)
    if profile is None:
        raise HTTPException(404, "No profile stored.")
    prefs = AllocationPreferences(
        self_rated_knowledge=profile.self_rated_knowledge or "LOW",
        max_lock_in_months=profile.max_lock_in_months,
    )
    corpus = Decimal(profile.liquid_balance or 0) + Decimal(
        profile.existing_investments or 0
    )
    return build_allocation(
        plan=plan,
        prefs=prefs,
        temperament=TemperamentChoice(profile.temperament_choice or "SELL_SOME"),
        corpus=corpus,
        cfg=load_vehicles(),
        inflation_pct=load_assumptions().inflation_expectation_pct,
    )


@router.get("/preferences")
async def get_preferences(
    session: AsyncSession = Depends(get_session),
) -> AllocationPreferences:
    profile = await session.get(Profile, 1)
    if profile is None:
        return AllocationPreferences()
    return AllocationPreferences(
        self_rated_knowledge=profile.self_rated_knowledge or "LOW",
        max_lock_in_months=profile.max_lock_in_months,
    )


@router.put("/preferences")
async def put_preferences(
    body: AllocationPreferences, session: AsyncSession = Depends(get_session)
) -> AllocationPreferences:
    profile = await session.get(Profile, 1)
    if profile is None:
        profile = Profile(id=1)
        session.add(profile)
    profile.self_rated_knowledge = body.self_rated_knowledge.value
    profile.max_lock_in_months = body.max_lock_in_months
    await session.commit()
    return body
