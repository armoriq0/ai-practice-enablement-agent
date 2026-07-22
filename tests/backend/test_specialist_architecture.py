import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from backend.app.agents import SupervisorAgent
from backend.app.agent_prompts import PROMPT_DIRECTORY, load_prompt
from backend.app.config import Settings
from backend.app.governance import ArmorIQGovernanceGateway
from backend.app.model_gateway import (
    DeterministicModelGateway,
    ModelBudget,
    OpenAIModelGateway,
)
from backend.app.specialists.research import ResearchOutput
from backend.app.tools import DeterministicWorkspaceAdapter, GovernedToolGateway


def build_supervisor() -> SupervisorAgent:
    settings = Settings(model_mode="deterministic")
    governance = ArmorIQGovernanceGateway(settings)
    tools = GovernedToolGateway(governance, DeterministicWorkspaceAdapter())
    return SupervisorAgent(
        governance,
        tools,
        settings=settings,
        model=DeterministicModelGateway(),
    )


def test_pipeline_uses_concrete_specialists_with_owned_contracts():
    supervisor = build_supervisor()
    agents = supervisor.pipeline

    assert len({type(agent) for agent in agents}) == len(agents)
    assert len({agent.spec.instructions for agent in agents}) == len(agents)
    assert len({agent.spec.output_type for agent in agents}) == len(agents)
    assert all(agent.allowed_tools == {agent.spec.tool} for agent in agents)
    assert all(agent.spec.budget.max_output_tokens > 0 for agent in agents)
    assert supervisor.discovery.allowed_tools == {"discover"}


def test_every_agent_instruction_comes_from_a_prompt_asset():
    supervisor = build_supervisor()
    prompt_names = {agent.spec.prompt_name for agent in supervisor.pipeline}
    prompt_names.add("discovery")

    assert prompt_names == {path.stem for path in PROMPT_DIRECTORY.glob("*.md")}
    assert all(load_prompt(name) for name in prompt_names)
    assert supervisor.discovery.instructions == load_prompt("discovery")
    assert all(
        agent.spec.instructions == load_prompt(agent.spec.prompt_name)
        for agent in supervisor.pipeline
    )


def test_prompt_loader_rejects_path_traversal():
    with pytest.raises(ValueError, match="Invalid agent prompt name"):
        load_prompt("../secrets")


@pytest.mark.asyncio
async def test_deterministic_gateway_enforces_agent_input_budget():
    gateway = DeterministicModelGateway()
    agent = build_supervisor().pipeline[0]

    with pytest.raises(ValueError, match="input exceeds"):
        await gateway.generate(
            agent=agent.name,
            instructions=agent.spec.instructions,
            payload={"oversized": "x" * 100},
            output_type=agent.spec.output_type,
            budget=ModelBudget(max_input_chars=10, max_output_tokens=100),
            fallback=ResearchOutput(evidence=[]),
        )


def test_openai_mode_fails_closed_without_credential():
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIModelGateway(Settings(model_mode="openai", openai_api_key=None))


@pytest.mark.asyncio
async def test_openai_gateway_uses_typed_responses_contract():
    gateway = OpenAIModelGateway(
        Settings(model_mode="openai", openai_api_key="test-key")
    )
    parsed = ResearchOutput(evidence=[])
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=parsed))
    gateway.client.responses.parse = parse

    result = await gateway.generate(
        agent="ResearchAgent",
        instructions="Research public sources.",
        payload={"domain": "example.com"},
        output_type=ResearchOutput,
        budget=ModelBudget(max_input_chars=1_000, max_output_tokens=321),
        fallback=parsed,
    )

    assert result is parsed
    assert parse.await_args.kwargs["text_format"] is ResearchOutput
    assert parse.await_args.kwargs["max_output_tokens"] == 321
    assert "untrusted data" in parse.await_args.kwargs["input"]
