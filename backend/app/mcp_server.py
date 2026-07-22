import hmac
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .config import get_settings
from .tools import DeterministicWorkspaceAdapter

PROTOCOL_VERSION = "2024-11-05"
TOOL_DESCRIPTIONS = {
    "discover": "Discover partner candidates autonomously with OpenAI web search.",
    "web_research": "Research public information about a partner candidate.",
    "evidence_validator": "Validate collected public evidence.",
    "scoring_model": "Score a candidate against the delegated partner profile.",
    "contact_search": "Identify a sourced public business contact.",
    "strategy_model": "Develop a partner engagement strategy.",
    "writing_model": "Draft evidence-grounded partner outreach.",
    "gmail_send": "Send an approved partner outreach email.",
    "gmail_reply_sync": "Read and classify a reply in the governed workflow.",
    "qualification_model": "Qualify a partner conversation.",
    "calendar_freebusy": "Find meeting availability.",
    "calendar_create": "Create an accepted meeting on the calendar.",
    "docs_create": "Create a meeting preparation brief.",
}
TOOLS = [
    {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "description": "Arguments bound to the ArmorIQ intent plan.",
            "additionalProperties": True,
        },
    }
    for name, description in TOOL_DESCRIPTIONS.items()
]


class JsonRpcRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jsonrpc: str
    id: str | int | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


settings = get_settings()
adapter = DeterministicWorkspaceAdapter()
app = FastAPI(title="ArmorIQ Partner Local Tools MCP", version="1.0.0")


def require_api_key(supplied: str | None) -> None:
    expected = settings.mcp_server_api_key
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid MCP API key")


def rpc_result(message_id: str | int | None, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def rpc_error(message_id: str | int | None, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "error": {"code": code, "message": message},
    }


async def dispatch(message: JsonRpcRequest) -> dict[str, Any]:
    if message.jsonrpc != "2.0":
        return rpc_error(message.id, -32600, "Invalid JSON-RPC version")
    if message.method == "initialize":
        return rpc_result(
            message.id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "armoriq-partner-local-tools",
                    "version": "1.0.0",
                },
            },
        )
    if message.method == "tools/list":
        return rpc_result(message.id, {"tools": TOOLS})
    if message.method == "tools/call":
        name = message.params.get("name")
        arguments = message.params.get("arguments", {})
        if name not in TOOL_DESCRIPTIONS:
            return rpc_error(message.id, -32602, "Unknown tool")
        if not isinstance(arguments, dict):
            return rpc_error(message.id, -32602, "Tool arguments must be an object")
        result = await adapter.invoke(str(name), arguments)
        return rpc_result(
            message.id,
            {"content": [{"type": "text", "text": json.dumps(result)}]},
        )
    return rpc_error(message.id, -32601, "Method not found")


def sse(payload: dict[str, Any]) -> AsyncIterator[str]:
    async def stream() -> AsyncIterator[str]:
        yield f"event: message\ndata: {json.dumps(payload)}\n\n"

    return stream()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/mcp")
async def mcp_endpoint(
    request: Request, x_api_key: str | None = Header(default=None)
) -> StreamingResponse:
    require_api_key(x_api_key)
    try:
        message = JsonRpcRequest.model_validate(await request.json())
        payload = await dispatch(message)
    except (ValueError, TypeError):
        payload = rpc_error(None, -32600, "Invalid request")
    return StreamingResponse(sse(payload), media_type="text/event-stream")
