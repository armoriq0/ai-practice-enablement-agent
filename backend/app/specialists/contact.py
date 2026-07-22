from pydantic import BaseModel

from ..model_gateway import ModelBudget
from ..models import AccountState, PartnerAccount
from .base import SpecialistAgent, SpecialistSpec


class BusinessContact(BaseModel):
    role: str
    email: str | None
    source: str | None


class ContactOutput(BaseModel):
    contact: BusinessContact
    contact_verified: bool


class ContactAgent(SpecialistAgent[ContactOutput]):
    spec = SpecialistSpec(
        name="ContactAgent",
        action="identify_contact",
        tool="contact_search",
        from_state=AccountState.SCORED,
        to_state=AccountState.CONTACTS_IDENTIFIED,
        prompt_name="contact",
        budget=ModelBudget(8_000, 3_000),
        output_type=ContactOutput,
        web_search=True,
    )

    def fallback(self, account: PartnerAccount) -> ContactOutput:
        email = account.data.get("public_business_email")
        source = account.data.get("contact_source")
        return ContactOutput(
            contact=BusinessContact(
                role="AI Practice Leader",
                email=str(email) if email else None,
                source=str(source) if source else None,
            ),
            contact_verified=bool(email and source),
        )
