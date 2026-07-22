from pydantic import BaseModel, Field

from ..model_gateway import ModelBudget
from ..models import AccountState, PartnerAccount
from .base import SpecialistAgent, SpecialistSpec


class OutreachDraftOutput(BaseModel):
    subject: str
    body: str
    claim_evidence: list[int] = Field(min_length=1)


class SendReadinessOutput(BaseModel):
    send_ready: bool
    reason: str


class OutreachDraftAgent(SpecialistAgent[OutreachDraftOutput]):
    spec = SpecialistSpec(
        name="OutreachAgent",
        action="generate_outreach",
        tool="writing_model",
        from_state=AccountState.STRATEGY_DRAFTED,
        to_state=AccountState.OUTREACH_DRAFTED,
        prompt_name="outreach_draft",
        budget=ModelBudget(14_000, 850),
        output_type=OutreachDraftOutput,
    )

    def fallback(self, account: PartnerAccount) -> OutreachDraftOutput:
        return OutreachDraftOutput(
            subject=f"Governed AI delivery for {account.name}",
            body="Explore an evidence-backed agent-assurance partnership.",
            claim_evidence=[0],
        )

    def validate_output(
        self, account: PartnerAccount, output: OutreachDraftOutput
    ) -> None:
        evidence_count = len(account.data.get("evidence", []))
        invalid = [
            index
            for index in output.claim_evidence
            if index < 0 or index >= evidence_count
        ]
        if invalid:
            raise ValueError(
                "outreach claim_evidence contains invalid zero-based indices: "
                f"{invalid} (evidence_count={evidence_count})"
            )


class OutreachSendAgent(SpecialistAgent[SendReadinessOutput]):
    spec = SpecialistSpec(
        name="OutreachAgent",
        action="send_email",
        tool="gmail_send",
        from_state=AccountState.OUTREACH_DRAFTED,
        to_state=AccountState.SENT,
        prompt_name="outreach_send",
        budget=ModelBudget(8_000, 300),
        output_type=SendReadinessOutput,
        risk="high",
    )

    def fallback(self, account: PartnerAccount) -> SendReadinessOutput:
        return SendReadinessOutput(
            send_ready=bool(account.data.get("contact_verified")),
            reason="Verified public business contact and evidence-backed draft",
        )
