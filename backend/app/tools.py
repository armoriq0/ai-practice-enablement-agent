import hashlib
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from .governance import ArmorIQGovernanceGateway
from .schemas import ActionRequest, Permit


class ToolAdapter(Protocol):
    async def invoke(
        self, operation: str, arguments: dict[str, Any]
    ) -> dict[str, Any]: ...


class DeterministicWorkspaceAdapter:
    """Safe local substitute for search/Gmail/Calendar/Drive in tests and demos."""

    async def invoke(self, operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
        identifier = hashlib.sha256(
            f"{operation}:{sorted(arguments.items())}".encode()
        ).hexdigest()[:16]
        if operation == "discover":
            return {"candidates": arguments.get("seed_candidates", [])}
        return {
            "external_id": f"local-{operation}-{identifier}",
            "status": "executed",
            "operation": operation,
        }


class GovernedToolGateway:
    def __init__(self, governance: ArmorIQGovernanceGateway, adapter: ToolAdapter):
        self.governance = governance
        self.adapter = adapter

    async def execute(
        self, db: AsyncSession, request: ActionRequest, permit: Permit
    ) -> dict[str, Any]:
        self.governance.validate_permit(permit, request)
        result = await self.adapter.invoke(request.tool, request.arguments)
        await self.governance.verify_execution(db, request, permit, result)
        return result
