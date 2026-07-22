import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent_prompts import load_prompt
from ..audit import append_audit
from ..governance import ArmorIQGovernanceGateway
from ..model_gateway import ModelBudget, ModelGateway
from ..models import AccountState, AgentRun, Mission, MissionStatus, PartnerAccount
from ..schemas import ActionRequest
from ..tools import GovernedToolGateway

OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass(frozen=True)
class SpecialistSpec(Generic[OutputT]):
    name: str
    action: str
    tool: str
    from_state: AccountState
    to_state: AccountState
    prompt_name: str
    budget: ModelBudget
    output_type: type[OutputT]
    risk: Literal["low", "medium", "high"] = "medium"
    web_search: bool = False

    @property
    def instructions(self) -> str:
        return load_prompt(self.prompt_name)


class SpecialistAgent(ABC, Generic[OutputT]):
    spec: SpecialistSpec[OutputT]

    def __init__(
        self,
        model: ModelGateway,
        governance: ArmorIQGovernanceGateway,
        tools: GovernedToolGateway,
    ):
        self.model = model
        self.governance = governance
        self.tools = tools

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def allowed_tools(self) -> frozenset[str]:
        return frozenset({self.spec.tool})

    @abstractmethod
    def fallback(self, account: PartnerAccount) -> OutputT:
        """Return a typed fixture used only by the explicit offline model adapter."""

    def model_payload(
        self, mission: Mission, account: PartnerAccount
    ) -> dict[str, object]:
        return {
            "mission_objective": mission.objective,
            "account": {
                "name": account.name,
                "domain": account.domain,
                "state": account.state.value,
                "data": account.data,
            },
        }

    def policy_context(
        self, mission: Mission, account: PartnerAccount, sent_count: int
    ) -> dict[str, object]:
        data = account.data
        return {
            "mission_running": mission.status == MissionStatus.RUNNING,
            "public_source": True,
            "no_prompt_injection": not data.get("prompt_injection", False),
            "prompt_injection": data.get("prompt_injection", False),
            "verified_evidence": account.state
            in {
                AccountState.EVIDENCE_VERIFIED,
                AccountState.SCORED,
                AccountState.CONTACTS_IDENTIFIED,
                AccountState.STRATEGY_DRAFTED,
                AccountState.OUTREACH_DRAFTED,
            },
            "business_contact": bool(
                data.get("public_business_email") and data.get("contact_source")
            ),
            "qualified_account": (account.score or 0) >= 70,
            "verified_contact": bool(data.get("contact_verified", False)),
            "evidence_coverage": bool(data.get("evidence")),
            "not_suppressed": not data.get("suppressed", False),
            "suppressed": data.get("suppressed", False),
            "within_send_limit": sent_count < mission.policy.get("max_outreach", 10),
            "positive_reply": data.get("reply_sentiment", "positive") == "positive",
            "within_delegation": True,
            "accepted_slot": data.get("accepted_slot", True),
            "verified_attendees": True,
            "meeting_booked": account.state == AccountState.MEETING_BOOKED,
        }

    def validate_output(self, account: PartnerAccount, output: OutputT) -> None:
        """Validate specialist-specific invariants before requesting authority."""
        del account, output

    async def run(
        self,
        db: AsyncSession,
        mission: Mission,
        account: PartnerAccount,
        sent_count: int,
        trace_id: str,
    ) -> str:
        if account.state != self.spec.from_state:
            raise ValueError(f"{self.name} cannot run from {account.state.value}")
        if self.spec.tool not in self.allowed_tools:
            raise PermissionError(f"{self.name} cannot use {self.spec.tool}")
        typed = await self.model.generate(
            agent=self.name,
            instructions=self.spec.instructions,
            payload=self.model_payload(mission, account),
            output_type=self.spec.output_type,
            budget=self.spec.budget,
            fallback=self.fallback(account),
            web_search=self.spec.web_search,
        )
        self.validate_output(account, typed)
        output = typed.model_dump(mode="json")
        arguments = {
            "account_id": account.id,
            "domain": account.domain,
            "state": account.state.value,
            "output": output,
        }
        request = ActionRequest(
            mission_id=mission.id,
            account_id=account.id,
            agent=self.name,
            action=self.spec.action,
            tool=self.spec.tool,
            arguments=arguments,
            evidence_ids=[
                str(i) for i, _ in enumerate(account.data.get("evidence", []))
            ],
            idempotency_key=(
                f"{mission.id}:{account.id}:{self.spec.action}:{account.state.value}"
            ),
            risk=self.spec.risk,
        )
        permit = await self.governance.authorize_tool_call(
            db, request, self.policy_context(mission, account, sent_count)
        )
        run = AgentRun(
            mission_id=mission.id,
            account_id=account.id,
            agent=self.name,
            status=permit.outcome,
            input=arguments,
            output=output if permit.outcome == "PERMIT" else {"reason": permit.reason},
            trace_id=trace_id,
        )
        db.add(run)
        if permit.outcome != "PERMIT":
            if permit.outcome == "DENY":
                account.state = AccountState.POLICY_DENIED
            await append_audit(
                db,
                mission.id,
                "agent.blocked",
                {
                    "agent": self.name,
                    "account_id": account.id,
                    "outcome": permit.outcome,
                    "reason": permit.reason,
                },
            )
            return permit.outcome
        result = await self.tools.execute(db, request, permit)
        merged = dict(account.data)
        merged.update(output)
        merged[f"{self.spec.tool}_result"] = result
        account.data = merged
        if "score" in output:
            account.score = float(output["score"])
            account.tier = str(output["tier"])
        account.state = self.spec.to_state
        run.status = "COMPLETED"
        await append_audit(
            db,
            mission.id,
            "state.transition",
            {
                "account_id": account.id,
                "agent": self.name,
                "from": self.spec.from_state.value,
                "to": self.spec.to_state.value,
                "permit_id": permit.permit_id,
            },
        )
        return "COMPLETED"


def new_trace_id() -> str:
    return str(uuid.uuid4())
