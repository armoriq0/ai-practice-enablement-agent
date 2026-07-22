from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent_prompts import load_prompt
from ..audit import append_audit
from ..governance import ArmorIQGovernanceGateway
from ..model_gateway import ModelBudget, ModelGateway
from ..models import Mission, PartnerAccount
from ..schemas import ActionRequest, Candidate
from ..tools import GovernedToolGateway


class DiscoveryOutput(BaseModel):
    candidates: list[Candidate] = Field(max_length=3)


class DiscoveryAgent:
    name = "DiscoveryAgent"
    instructions = load_prompt("discovery")
    allowed_tools = frozenset({"discover"})
    budget = ModelBudget(12_000, 4_000)
    output_type = DiscoveryOutput

    def __init__(
        self,
        model: ModelGateway,
        governance: ArmorIQGovernanceGateway,
        tools: GovernedToolGateway,
    ):
        self.model = model
        self.governance = governance
        self.tools = tools

    async def run(
        self, db: AsyncSession, mission: Mission, candidates: list[Candidate]
    ) -> list[PartnerAccount]:
        existing_domains = list(
            await db.scalars(
                select(PartnerAccount.domain).where(
                    PartnerAccount.mission_id == mission.id
                )
            )
        )
        fallback = DiscoveryOutput(candidates=candidates)
        typed = await self.model.generate(
            agent=self.name,
            instructions=self.instructions,
            payload={
                "mission_objective": mission.objective,
                "mission_policy": mission.policy,
                "candidate_limit": min(
                    int(mission.policy.get("max_outreach", 10)), 3
                ),
                "exclude_domains": existing_domains,
                "seed_candidates": [c.model_dump(mode="json") for c in candidates],
            },
            output_type=self.output_type,
            budget=self.budget,
            fallback=fallback,
            web_search=True,
        )
        request = ActionRequest(
            mission_id=mission.id,
            agent=self.name,
            action="discover_partners",
            tool="discover",
            arguments={
                "seed_candidates": [c.model_dump(mode="json") for c in typed.candidates],
                "source": "openai_web_search",
            },
            idempotency_key=f"{mission.id}:discover",
        )
        permit = await self.governance.authorize_tool_call(
            db, request, {"mission_running": True}
        )
        if permit.outcome != "PERMIT":
            await append_audit(
                db,
                mission.id,
                "agent.blocked",
                {
                    "agent": self.name,
                    "outcome": permit.outcome,
                    "reason": permit.reason,
                },
            )
            return []
        result = await self.tools.execute(db, request, permit)
        accounts = []
        for value in result["candidates"]:
            existing = await db.scalar(
                select(PartnerAccount).where(
                    PartnerAccount.mission_id == mission.id,
                    PartnerAccount.domain == value["domain"],
                )
            )
            if not existing:
                existing = PartnerAccount(
                    mission_id=mission.id,
                    name=value["name"],
                    domain=value["domain"],
                    data={
                        "category": value["category"],
                        "public_business_email": value.get("public_business_email"),
                        "contact_source": value.get("contact_source"),
                    },
                )
                db.add(existing)
                await db.flush()
            accounts.append(existing)
        return accounts
