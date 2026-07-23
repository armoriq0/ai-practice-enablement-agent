import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api import app
from backend.app.db import create_schema


@pytest.mark.asyncio
async def test_autonomous_mission_reaches_meeting_with_armoriq_permits():
    await create_schema()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/missions",
            json={
                "objective": "Secure qualified meetings with AI assurance consulting partners",
                "target_meetings": 1,
                "max_outreach": 2,
            },
        )
        assert created.status_code == 201
        mission_id = created.json()["id"]
        completed = await client.post(
            f"/api/v1/missions/{mission_id}/run",
            json={
                "candidates": [
                    {
                        "name": "Northstar",
                        "domain": "northstar.example",
                        "category": "ai_consulting",
                        "public_business_email": "partnerships@northstar.example",
                        "contact_source": "https://northstar.example/contact",
                    }
                ]
            },
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "COMPLETED"
        accounts = (await client.get(f"/api/v1/missions/{mission_id}/accounts")).json()
        assert accounts[0]["state"] == "MEETING_BRIEF_CREATED"
        decisions = (
            await client.get(f"/api/v1/missions/{mission_id}/policy-decisions")
        ).json()
        assert decisions and all(value["outcome"] == "PERMIT" for value in decisions)
        assert any(value["action"] == "send_email" for value in decisions)
        audit = (await client.get(f"/api/v1/missions/{mission_id}/audit")).json()
        assert audit["valid"] is True


@pytest.mark.asyncio
async def test_unsourced_contact_is_denied_before_outreach():
    await create_schema()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/missions",
            json={"objective": "Find a partner without inventing any contact details"},
        )
        mission_id = created.json()["id"]
        await client.post(
            f"/api/v1/missions/{mission_id}/run",
            json={
                "candidates": [
                    {
                        "name": "Unknown",
                        "domain": "unknown.example",
                        "category": "cloud",
                    }
                ]
            },
        )
        accounts = (await client.get(f"/api/v1/missions/{mission_id}/accounts")).json()
        assert accounts[0]["state"] == "POLICY_DENIED"
        decisions = (
            await client.get(f"/api/v1/missions/{mission_id}/policy-decisions")
        ).json()
        assert any(
            value["action"] == "identify_contact" and value["outcome"] == "DENY"
            for value in decisions
        )
        assert not any(value["action"] == "send_email" for value in decisions)


@pytest.mark.asyncio
async def test_operator_seed_list_is_not_truncated_to_discovery_limit():
    await create_schema()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/missions",
            json={
                "objective": "Evaluate the complete operator-provided partner list",
                "max_outreach": 10,
            },
        )
        mission_id = created.json()["id"]
        candidates = [
            {
                "name": f"Seed {index}",
                "domain": f"seed-{index}.example",
                "category": "ai_consulting",
            }
            for index in range(5)
        ]
        response = await client.post(
            f"/api/v1/missions/{mission_id}/run", json={"candidates": candidates}
        )
        assert response.status_code == 200
        accounts = (await client.get(f"/api/v1/missions/{mission_id}/accounts")).json()
        assert {account["domain"] for account in accounts} == {
            candidate["domain"] for candidate in candidates
        }
