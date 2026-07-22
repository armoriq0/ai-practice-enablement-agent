from pydantic import BaseModel

from ..model_gateway import ModelBudget
from ..models import AccountState, PartnerAccount
from .base import SpecialistAgent, SpecialistSpec


class MeetingBriefOutput(BaseModel):
    title: str
    objectives: list[str]
    evidence_summary: str


class MeetingPreparationAgent(SpecialistAgent[MeetingBriefOutput]):
    spec = SpecialistSpec(
        name="MeetingPreparationAgent",
        action="create_meeting_brief",
        tool="docs_create",
        from_state=AccountState.MEETING_BOOKED,
        to_state=AccountState.MEETING_BRIEF_CREATED,
        prompt_name="meeting_preparation",
        budget=ModelBudget(16_000, 1_000),
        output_type=MeetingBriefOutput,
    )

    def fallback(self, account: PartnerAccount) -> MeetingBriefOutput:
        return MeetingBriefOutput(
            title=f"ArmorIQ partnership discussion with {account.name}",
            objectives=["Validate partner fit", "Agree on a governed AI pilot"],
            evidence_summary="Enterprise AI and security services alignment verified.",
        )
