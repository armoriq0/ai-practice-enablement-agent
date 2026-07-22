from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from ..model_gateway import ModelBudget
from ..models import AccountState, PartnerAccount
from .base import SpecialistAgent, SpecialistSpec


class EvidenceItem(BaseModel):
    url: str
    claim: str
    public: bool

    @field_validator("url")
    @classmethod
    def require_public_http_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("evidence URL must be an absolute HTTP(S) URL")
        return value


class ResearchOutput(BaseModel):
    evidence: list[EvidenceItem] = Field(max_length=5)


class ResearchAgent(SpecialistAgent[ResearchOutput]):
    spec = SpecialistSpec(
        name="ResearchAgent",
        action="research_company",
        tool="web_research",
        from_state=AccountState.DISCOVERED,
        to_state=AccountState.RESEARCHED,
        prompt_name="research",
        budget=ModelBudget(12_000, 4_000),
        output_type=ResearchOutput,
        web_search=True,
    )

    def fallback(self, account: PartnerAccount) -> ResearchOutput:
        return ResearchOutput(
            evidence=[
                EvidenceItem.model_validate(
                    {
                        "url": f"https://{account.domain}/services",
                        "claim": (
                            f"{account.name} provides enterprise AI and security services"
                        ),
                        "public": True,
                    }
                )
            ]
        )
