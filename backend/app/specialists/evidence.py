from pydantic import BaseModel

from ..model_gateway import ModelBudget
from ..models import AccountState, PartnerAccount
from .base import SpecialistAgent, SpecialistSpec


class EvidenceVerificationOutput(BaseModel):
    evidence_verified: bool
    prompt_injection: bool


class EvidenceAgent(SpecialistAgent[EvidenceVerificationOutput]):
    spec = SpecialistSpec(
        name="EvidenceAgent",
        action="accept_evidence",
        tool="evidence_validator",
        from_state=AccountState.RESEARCHED,
        to_state=AccountState.EVIDENCE_VERIFIED,
        prompt_name="evidence",
        budget=ModelBudget(16_000, 500),
        output_type=EvidenceVerificationOutput,
    )

    def fallback(self, account: PartnerAccount) -> EvidenceVerificationOutput:
        return EvidenceVerificationOutput(
            evidence_verified=bool(account.data.get("evidence")),
            prompt_injection=bool(account.data.get("prompt_injection", False)),
        )
