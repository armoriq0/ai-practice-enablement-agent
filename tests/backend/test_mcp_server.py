import json

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.mcp_server import TOOL_DESCRIPTIONS, app, settings


def parse_sse(body: str) -> dict:
    data = next(
        line.removeprefix("data: ")
        for line in body.splitlines()
        if line.startswith("data: ")
    )
    return json.loads(data)


@pytest.mark.asyncio
async def test_mcp_requires_api_key_and_lists_local_tools():
    settings.mcp_server_api_key = "test-mcp-key"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        unauthorized = await client.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        )
        assert unauthorized.status_code == 401

        response = await client.post(
            "/mcp",
            headers={"X-API-Key": "test-mcp-key"},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        payload = parse_sse(response.text)
        assert {tool["name"] for tool in payload["result"]["tools"]} == set(
            TOOL_DESCRIPTIONS
        )


@pytest.mark.asyncio
async def test_mcp_initializes_and_calls_adapter():
    settings.mcp_server_api_key = "test-mcp-key"
    headers = {"X-API-Key": "test-mcp-key"}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        initialized = await client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            },
        )
        assert parse_sse(initialized.text)["result"]["capabilities"] == {"tools": {}}

        called = await client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "discover",
                    "arguments": {"seed_candidates": [{"name": "Example"}]},
                },
            },
        )
        result = parse_sse(called.text)["result"]["content"]
        assert json.loads(result[0]["text"])["candidates"] == [{"name": "Example"}]
