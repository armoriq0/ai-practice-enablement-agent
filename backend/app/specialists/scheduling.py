from datetime import datetime

from pydantic import BaseModel

from ..model_gateway import ModelBudget
from ..models import AccountState, PartnerAccount
from .base import SpecialistAgent, SpecialistSpec


class MeetingProposalOutput(BaseModel):
    proposed_slots: list[datetime]
    accepted_slot: bool


class CalendarBookingOutput(BaseModel):
    booking_ready: bool
    attendee_verified: bool


class MeetingProposalAgent(SpecialistAgent[MeetingProposalOutput]):
    spec = SpecialistSpec(
        name="SchedulingAgent",
        action="propose_meeting",
        tool="calendar_freebusy",
        from_state=AccountState.QUALIFIED,
        to_state=AccountState.MEETING_PROPOSED,
        prompt_name="meeting_proposal",
        budget=ModelBudget(7_000, 400),
        output_type=MeetingProposalOutput,
        risk="high",
    )

    def fallback(self, account: PartnerAccount) -> MeetingProposalOutput:
        del account
        return MeetingProposalOutput(
            proposed_slots=[datetime.fromisoformat("2026-08-03T15:00:00+00:00")],
            accepted_slot=True,
        )


class CalendarBookingAgent(SpecialistAgent[CalendarBookingOutput]):
    spec = SpecialistSpec(
        name="SchedulingAgent",
        action="create_calendar_event",
        tool="calendar_create",
        from_state=AccountState.MEETING_PROPOSED,
        to_state=AccountState.MEETING_BOOKED,
        prompt_name="calendar_booking",
        budget=ModelBudget(7_000, 300),
        output_type=CalendarBookingOutput,
        risk="high",
    )

    def fallback(self, account: PartnerAccount) -> CalendarBookingOutput:
        return CalendarBookingOutput(
            booking_ready=bool(account.data.get("accepted_slot", True)),
            attendee_verified=bool(account.data.get("contact_verified")),
        )
