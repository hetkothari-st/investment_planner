"""Load user state, compute plans, persist plan_versions."""

import json
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from corpus.db.models import Debt, Goal, PlanVersion, Profile
from corpus.planner.engine import compute_plan
from corpus.planner.schemas import DebtIn, GoalIn, PlanInput, PlanResult, ProfileIn


class ProfileIncomplete(Exception):
    """Raised when the stored profile is missing the fields a plan needs."""


async def load_plan_input(session: AsyncSession, as_of: date) -> PlanInput:
    profile = await session.get(Profile, 1)
    required = ("monthly_inflow", "fixed_outflow", "variable_outflow", "liquid_balance")
    if profile is None or any(getattr(profile, f) is None for f in required):
        raise ProfileIncomplete(
            "Profile needs monthly inflow, fixed and variable outflow, and liquid "
            "balance before a plan can be computed."
        )
    debts = (await session.execute(select(Debt))).scalars().all()
    goals = (await session.execute(select(Goal))).scalars().all()
    return PlanInput(
        profile=ProfileIn(
            display_name=profile.display_name,
            monthly_inflow=profile.monthly_inflow,
            fixed_outflow=profile.fixed_outflow,
            variable_outflow=profile.variable_outflow,
            liquid_balance=profile.liquid_balance,
            existing_investments=profile.existing_investments or 0,
            dependants=profile.dependants or 0,
            job_stability=profile.job_stability or "MEDIUM",
            income_variability=profile.income_variability or 0,
            temperament_choice=profile.temperament_choice or "SELL_SOME",
        ),
        debts=[
            DebtIn(
                label=d.label,
                principal_outstanding=d.principal_outstanding,
                annual_rate_pct=d.annual_rate_pct,
                min_emi=d.min_emi or 0,
                tax_deductible=d.tax_deductible or False,
            )
            for d in debts
        ],
        goals=[
            GoalIn(
                label=g.label,
                target_amount=g.target_amount,
                target_date=g.target_date,
                priority=g.priority or "SHOULD",
            )
            for g in goals
        ],
        as_of=as_of,
    )


def rationale_md(result: PlanResult) -> str:
    """Deterministic, templated. The plan explains itself without an LLM."""
    lines = ["## Plan rationale", ""]
    for g in result.gates:
        lines.append(f"- **{g.gate} {g.label}** [{g.status}] ₹{g.amount}: {g.reason}")
    if result.blocking_reasons:
        lines += ["", "### Blocking", ""]
        lines += [f"- {b}" for b in result.blocking_reasons]
    lines += [
        "",
        f"Investable: ₹{result.investable_monthly}/month, ₹{result.investable_lumpsum} lumpsum. "
        f"Assumptions {result.assumptions_version}.",
    ]
    return "\n".join(lines)


async def compute_and_persist(session: AsyncSession, as_of: date) -> PlanResult:
    inp = await load_plan_input(session, as_of)
    result = compute_plan(inp)

    version = PlanVersion(
        id=uuid.uuid4(),
        profile_snapshot=_as_db_json(session, inp.model_dump(mode="json")),
        plan_result=_as_db_json(session, result.model_dump(mode="json")),
        rationale_md=rationale_md(result),
    )
    # supersede the previous latest
    prev = (
        await session.execute(
            select(PlanVersion)
            .where(PlanVersion.superseded_by.is_(None))
            .order_by(PlanVersion.created_at.desc())
        )
    ).scalars().first()
    if prev is not None:
        prev.superseded_by = version.id
    session.add(version)
    await session.commit()

    result.version_id = version.id
    result.generated_at = datetime.now(UTC)
    return result


async def latest_plan(session: AsyncSession) -> PlanResult | None:
    row = (
        await session.execute(
            select(PlanVersion)
            .where(PlanVersion.superseded_by.is_(None))
            .order_by(PlanVersion.created_at.desc())
        )
    ).scalars().first()
    if row is None:
        return None
    raw = row.plan_result
    if isinstance(raw, str):  # sqlite stores JSON as text
        raw = json.loads(raw)
    result = PlanResult.model_validate(raw)
    result.version_id = row.id
    result.generated_at = row.created_at
    return result


def _as_db_json(session: AsyncSession, payload: dict) -> dict | str:
    return json.dumps(payload) if session.bind.dialect.name == "sqlite" else payload
