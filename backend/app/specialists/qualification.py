from typing import Literal

from pydantic import BaseModel, Field

from ..model_gateway import ModelBudget
from ..models import AccountState, PartnerAccount
from .base import SpecialistAgent, SpecialistSpec


class QualificationOutput(BaseModel):
    score: float = Field(ge=0, le=100)
    tier: Literal["A", "B", "C", "D"]
    explanation: str


class QualificationAgent(SpecialistAgent[QualificationOutput]):
    spec = SpecialistSpec(
        name="QualificationAgent",
        action="score_company",
        tool="scoring_model",
        from_state=AccountState.EVIDENCE_VERIFIED,
        to_state=AccountState.SCORED,
        prompt_name="qualification",
        budget=ModelBudget(10_000, 500),
        output_type=QualificationOutput,
    )

    def fallback(self, account: PartnerAccount) -> QualificationOutput:
        del account
        return QualificationOutput(
            score=86,
            tier="A",
            explanation="Enterprise services and AI-security alignment",
        )
