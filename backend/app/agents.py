from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .audit import append_audit
from .config import Settings, get_settings
from .governance import ArmorIQGovernanceGateway
from .model_gateway import ModelGateway, build_model_gateway
from .models import AccountState, Mission, MissionStatus, PartnerAccount
from .schemas import Candidate
from .specialists import (
    CalendarBookingAgent,
    ContactAgent,
    ConversationQualificationAgent,
    DiscoveryAgent,
    EvidenceAgent,
    MeetingPreparationAgent,
    MeetingProposalAgent,
    OutreachDraftAgent,
    OutreachSendAgent,
    QualificationAgent,
    ReplyClassificationAgent,
    ResearchAgent,
    StrategyAgent,
)
from .specialists.base import SpecialistAgent, new_trace_id
from .tools import GovernedToolGateway


class SupervisorAgent:
    PLAN = [
        "discover",
        "research",
        "verify evidence",
        "score",
        "identify contact",
        "develop strategy",
        "draft and send",
        "manage reply",
        "schedule",
        "prepare brief",
    ]

    def __init__(
        self,
        governance: ArmorIQGovernanceGateway,
        tools: GovernedToolGateway,
        settings: Settings | None = None,
        model: ModelGateway | None = None,
    ):
        self.governance = governance
        self.tools = tools
        self.settings = settings or get_settings()
        self.model = model or build_model_gateway(self.settings)
        self.discovery = DiscoveryAgent(self.model, governance, tools)
        self.pipeline: tuple[SpecialistAgent, ...] = (
            ResearchAgent(self.model, governance, tools),
            EvidenceAgent(self.model, governance, tools),
            QualificationAgent(self.model, governance, tools),
            ContactAgent(self.model, governance, tools),
            StrategyAgent(self.model, governance, tools),
            OutreachDraftAgent(self.model, governance, tools),
            OutreachSendAgent(self.model, governance, tools),
            ReplyClassificationAgent(self.model, governance, tools),
            ConversationQualificationAgent(self.model, governance, tools),
            MeetingProposalAgent(self.model, governance, tools),
            CalendarBookingAgent(self.model, governance, tools),
            MeetingPreparationAgent(self.model, governance, tools),
        )

    async def run(
        self, db: AsyncSession, mission: Mission, candidates: list[Candidate]
    ) -> Mission:
        mission.status = MissionStatus.RUNNING
        await self.governance.capture_purpose(db, mission.id, mission.objective)
        await self.governance.capture_plan(db, mission.id, self.PLAN)
        accounts = await self.discovery.run(db, mission, candidates)
        trace_id = new_trace_id()
        actions = 0
        for account in accounts:
            sent_count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(PartnerAccount)
                    .where(
                        PartnerAccount.mission_id == mission.id,
                        PartnerAccount.state.in_(
                            [
                                AccountState.SENT,
                                AccountState.REPLIED,
                                AccountState.QUALIFIED,
                                AccountState.MEETING_PROPOSED,
                                AccountState.MEETING_BOOKED,
                                AccountState.MEETING_BRIEF_CREATED,
                            ]
                        ),
                    )
                )
                or 0
            )
            for agent in self.pipeline:
                if (
                    account.state != agent.spec.from_state
                    or actions >= self.settings.max_actions_per_run
                ):
                    continue
                outcome = await agent.run(db, mission, account, sent_count, trace_id)
                actions += 1
                if outcome != "COMPLETED":
                    break
                if agent.spec.to_state == AccountState.SENT:
                    sent_count += 1
        terminal = bool(accounts) and all(
            account.state
            in {
                AccountState.MEETING_BRIEF_CREATED,
                AccountState.DISQUALIFIED,
                AccountState.POLICY_DENIED,
            }
            for account in accounts
        )
        mission.status = MissionStatus.COMPLETED if terminal else MissionStatus.PAUSED
        mission.metrics = {
            "accounts": len(accounts),
            "actions": actions,
            "meetings": sum(
                a.state == AccountState.MEETING_BRIEF_CREATED for a in accounts
            ),
            "qualified": sum((a.score or 0) >= 70 for a in accounts),
        }
        await append_audit(
            db,
            mission.id,
            "mission.finished",
            {"status": mission.status.value, "metrics": mission.metrics},
        )
        await db.commit()
        return mission
