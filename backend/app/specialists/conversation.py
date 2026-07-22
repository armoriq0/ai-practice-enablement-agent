from pydantic import BaseModel

from ..model_gateway import ModelBudget
from ..models import AccountState, PartnerAccount
from .base import SpecialistAgent, SpecialistSpec


class ReplyClassificationOutput(BaseModel):
    reply_sentiment: str
    sequence_stopped: bool


class ConversationQualificationOutput(BaseModel):
    qualified: bool
    need: str


class ReplyClassificationAgent(SpecialistAgent[ReplyClassificationOutput]):
    spec = SpecialistSpec(
        name="ConversationAgent",
        action="classify_reply",
        tool="gmail_reply_sync",
        from_state=AccountState.SENT,
        to_state=AccountState.REPLIED,
        prompt_name="reply_classification",
        budget=ModelBudget(10_000, 400),
        output_type=ReplyClassificationOutput,
    )

    def fallback(self, account: PartnerAccount) -> ReplyClassificationOutput:
        del account
        return ReplyClassificationOutput(
            reply_sentiment="positive", sequence_stopped=True
        )


class ConversationQualificationAgent(SpecialistAgent[ConversationQualificationOutput]):
    spec = SpecialistSpec(
        name="ConversationAgent",
        action="classify_reply",
        tool="qualification_model",
        from_state=AccountState.REPLIED,
        to_state=AccountState.QUALIFIED,
        prompt_name="conversation_qualification",
        budget=ModelBudget(10_000, 450),
        output_type=ConversationQualificationOutput,
    )

    def fallback(self, account: PartnerAccount) -> ConversationQualificationOutput:
        del account
        return ConversationQualificationOutput(
            qualified=True, need="governed enterprise AI delivery"
        )
