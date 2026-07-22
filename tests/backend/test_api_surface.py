import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api import app
from backend.app.db import create_schema


@pytest.mark.asyncio
async def test_control_plane_surface_and_mission_controls():
    await create_schema()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/health")).json()["status"] == "ok"
        assert (await client.get("/api/v1/health")).status_code == 200
        assert (await client.get("/api/v1/readiness")).json()["database"] == "ok"
        assert (
            await client.post("/api/v1/tasks/scheduled/discovery")
        ).status_code == 202
        assert (await client.post("/api/v1/tasks/scheduled/unknown")).status_code == 404

        created = await client.post(
            "/api/v1/missions",
            json={
                "name": "Autonomous test",
                "objective": "Secure qualified partner meetings autonomously",
            },
        )
        mission_id = created.json()["id"]
        assert (await client.get("/api/v1/missions")).json()
        assert (await client.get(f"/api/v1/missions/{mission_id}")).status_code == 200
        assert (await client.get("/api/v1/missions/missing")).status_code == 404
        # The offline adapter has no web access, so seedless autonomous discovery
        # safely pauses. MODEL_MODE=openai performs the real search in production.
        assert (await client.post(f"/api/v1/missions/{mission_id}/start")).json()[
            "status"
        ] == "PAUSED"
        assert (await client.post(f"/api/v1/missions/{mission_id}/pause")).json()[
            "status"
        ] == "PAUSED"
        assert (await client.post(f"/api/v1/missions/{mission_id}/resume")).json()[
            "status"
        ] == "PAUSED"
        assert (await client.post(f"/api/v1/missions/{mission_id}/stop")).json()[
            "status"
        ] == "PAUSED"
        assert (await client.get("/api/v1/agent-runs")).json() == []
        assert (await client.get("/api/v1/policy-decisions")).json()
        assert (await client.get("/api/v1/escalations")).status_code == 200
        assert (await client.get("/api/v1/audit")).json()


@pytest.mark.asyncio
async def test_non_delegated_mission_cannot_run():
    await create_schema()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/missions",
            json={
                "objective": "Create a bounded plan without execution",
                "auto_execute": False,
            },
        )
        response = await client.post(
            f"/api/v1/missions/{created.json()['id']}/run", json={"candidates": []}
        )
        assert response.status_code == 409
