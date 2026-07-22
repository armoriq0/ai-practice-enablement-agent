from pydantic import BaseModel

from ..model_gateway import ModelBudget
from ..models import AccountState, PartnerAccount
from .base import SpecialistAgent, SpecialistSpec


class StrategyOutput(BaseModel):
    strategy: str
    value_hypothesis: str


class StrategyAgent(SpecialistAgent[StrategyOutput]):
    spec = SpecialistSpec(
        name="StrategyAgent",
        action="generate_outreach",
        tool="strategy_model",
        from_state=AccountState.CONTACTS_IDENTIFIED,
        to_state=AccountState.STRATEGY_DRAFTED,
        prompt_name="strategy",
        budget=ModelBudget(12_000, 700),
        output_type=StrategyOutput,
    )

    def fallback(self, account: PartnerAccount) -> StrategyOutput:
        del account
        return StrategyOutput(
            strategy=(
                "Position governed production AI as a differentiated consulting offering"
            ),
            value_hypothesis="ArmorIQ can make agent actions policy-bound and auditable.",
        )
