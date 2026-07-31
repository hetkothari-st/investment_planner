"""Planner API flow on the test DB: paise transport, persistence, 409 gating."""

import httpx
import pytest

from corpus.api.main import create_app
from corpus.db.session import get_session


@pytest.fixture
async def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


PROFILE_PAISE = {
    # ₹2,00,000 inflow etc — integer paise in JSON transport
    "monthly_inflow": 20_000_000,
    "fixed_outflow": 6_000_000,
    "variable_outflow": 4_000_000,
    "liquid_balance": 4_000_000,  # ₹40,000 — under the buffer target
    "existing_investments": 0,
    "dependants": 0,
    "job_stability": "MEDIUM",
    "income_variability": "0.05",
    "temperament_choice": "HOLD",
}


async def test_plan_requires_profile(client):
    resp = await client.post("/planner/plan")
    assert resp.status_code == 409
    assert "profile" in resp.json()["detail"].lower()


async def test_full_flow_unfunded_buffer(client):
    assert (await client.put("/planner/profile", json=PROFILE_PAISE)).status_code == 200
    resp = await client.post("/planner/plan")
    assert resp.status_code == 200
    plan = resp.json()

    assert plan["investable_monthly"] == 0
    assert any("Emergency buffer" in b for b in plan["blocking_reasons"])
    g3 = next(g for g in plan["gates"] if g["gate"] == "G3")
    assert g3["status"] == "BLOCKED"
    # paise transport: G3 routes the whole ₹1,00,000 surplus
    assert g3["amount"] == 10_000_000

    latest = (await client.get("/planner/plan/latest")).json()
    assert latest["blocking_reasons"] == plan["blocking_reasons"]
    assert latest["version_id"] == plan["version_id"]


async def test_funded_profile_invests_and_supersedes(client):
    await client.put("/planner/profile", json=PROFILE_PAISE)
    await client.post("/planner/plan")

    funded = PROFILE_PAISE | {"liquid_balance": 100_000_000}  # ₹10,00,000
    await client.put("/planner/profile", json=funded)
    plan = (await client.post("/planner/plan")).json()
    assert plan["blocking_reasons"] == []
    assert plan["investable_monthly"] == 10_000_000  # ₹1,00,000 in paise

    latest = (await client.get("/planner/plan/latest")).json()
    assert latest["version_id"] == plan["version_id"]  # old version superseded


async def test_temperament_scenario_scales_to_corpus(client):
    await client.put(
        "/planner/profile", json=PROFILE_PAISE | {"liquid_balance": 100_000_000}
    )
    scenario = (await client.get("/planner/temperament-scenario")).json()
    assert scenario["before_inr"] == 1_000_000  # rupees, the user's actual corpus
    assert scenario["after_inr"] == 550_000  # after the assumed 45% drawdown
    assert len(scenario["options"]) == 4
