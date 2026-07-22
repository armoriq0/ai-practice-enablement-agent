import pytest
from types import SimpleNamespace
from httpx import ASGITransport, AsyncClient

from backend.app.api import app
from backend.app.config import Settings
from backend.app.db import SessionLocal, create_schema
from backend.app.governance import ArmorIQGovernanceGateway
from backend.app.models import Mission, PolicyDecision
from backend.app.schemas import ActionRequest


def request(**changes):
    values = {
        "mission_id": "m1",
        "account_id": "a1",
        "agent": "OutreachAgent",
        "action": "send_email",
        "tool": "gmail_send",
        "arguments": {"to": "partner@example.com", "body": "hello"},
        "evidence_ids": ["e1"],
        "idempotency_key": "once",
        "risk": "high",
    }
    values.update(changes)
    return ActionRequest(**values)


def research_request(**changes):
    values = {
        "action": "research_company",
        "tool": "web_research",
        "arguments": {"domain": "example.com"},
        "risk": "low",
    }
    values.update(changes)
    return request(**values)


def test_policy_denies_suppressed_recipient():
    gateway = ArmorIQGovernanceGateway(Settings())
    outcome, reason = gateway._evaluate(
        research_request(), {"mission_running": True, "suppressed": True}
    )
    assert outcome == "DENY"
    assert "suppressed" in reason.lower()


def test_policy_replans_when_evidence_is_missing():
    gateway = ArmorIQGovernanceGateway(Settings())
    outcome, _ = gateway._evaluate(
        request(action="generate_outreach", tool="writing_model"),
        {
            "qualified_account": True,
        },
    )
    assert outcome == "REPLAN"


def test_unknown_action_and_sensitive_recipient_are_blocked():
    gateway = ArmorIQGovernanceGateway(Settings())
    assert gateway._evaluate(request(action="unknown"), {})[0] == "DENY"
    assert (
        gateway._evaluate(research_request(), {"sensitive_recipient": True})[0]
        == "ESCALATE"
    )


def test_permit_is_required_and_bound_to_exact_inputs():
    gateway = ArmorIQGovernanceGateway(Settings())
    from backend.app.schemas import Permit

    denied = Permit(
        permit_id="p",
        outcome="DENY",
        reason="denied",
        action="send_email",
        tool="gmail_send",
        agent="OutreachAgent",
        input_hash="x",
    )
    with pytest.raises(PermissionError):
        gateway.validate_permit(denied, request())


@pytest.mark.asyncio
async def test_allow_escalation_requires_fresh_authorization_and_is_single_use():
    await create_schema()
    async with SessionLocal() as db:
        mission = Mission(
            objective="Resolve a sensitive action without creating a policy bypass"
        )
        db.add(mission)
        await db.flush()
        decision = PolicyDecision(
            mission_id=mission.id,
            action="send_email",
            outcome="ESCALATE",
            reason="Sensitive recipient",
            input_hash="a" * 64,
            context={},
        )
        db.add(decision)
        await db.commit()
        decision_id = decision.id
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resolved = await client.post(
            f"/api/v1/escalations/{decision_id}/resolve", json={"resolution": "allow"}
        )
        assert resolved.status_code == 200
        assert resolved.json()["permit_issued"] is False
        assert (
            resolved.json()["next_step"] == "fresh_action_bound_authorization_required"
        )
        repeated = await client.post(
            f"/api/v1/escalations/{decision_id}/resolve", json={"resolution": "allow"}
        )
        assert repeated.status_code == 409


@pytest.mark.asyncio
async def test_signed_permit_rejects_signature_and_input_tampering():
    await create_schema()
    gateway = ArmorIQGovernanceGateway(Settings())
    async with SessionLocal() as db:
        mission = Mission(objective="Issue an exact action authorization for testing")
        db.add(mission)
        await db.flush()
        original = research_request(mission_id=mission.id)
        permit = await gateway.authorize_tool_call(
            db,
            original,
            {"mission_running": True},
        )
        gateway.validate_permit(permit, original)
        changed = research_request(
            mission_id=mission.id, arguments={"domain": "different.example"}
        )
        with pytest.raises(PermissionError):
            gateway.validate_permit(permit, changed)
        replacement = "0" if permit.token[-1] != "0" else "1"
        permit.token = f"{permit.token[:-1]}{replacement}"
        with pytest.raises(PermissionError):
            gateway.validate_permit(permit, original)


@pytest.mark.asyncio
async def test_live_armoriq_fails_closed_without_configuration():
    gateway = ArmorIQGovernanceGateway(
        Settings(armoriq_mode="remote", armoriq_api_key=None, _env_file=None)
    )
    outcome, reason = await gateway._remote_evaluate(request(), {})
    assert outcome == "DENY" and "not configured" in reason


@pytest.mark.asyncio
async def test_live_armoriq_sdk_decision_is_used():
    class Session:
        closed = False

        def start_plan(self, tool_calls, goal):
            assert tool_calls == [
                {"name": "web_research", "args": research_request().arguments}
            ]
            assert "research_company" in goal
            return SimpleNamespace(plan_id="plan-1", token_id="token-1", plan_hash="h")

        def check(self, tool_name, arguments, user_email=None):
            assert tool_name == "web_research"
            assert arguments == research_request().arguments
            assert user_email is None
            return SimpleNamespace(
                allowed=True,
                action="allow",
                reason="SDK policy permitted the bounded action",
                matched_policy="test-policy",
                obligations=[],
            )

        def close(self):
            self.closed = True

    class Client:
        def __init__(self):
            self.session = Session()

        def start_session(self, options):
            assert options.mode == "sdk"
            return self.session

    client = Client()
    gateway = ArmorIQGovernanceGateway(
        Settings(
            armoriq_mode="remote",
            armoriq_api_key="secret",
            _env_file=None,
        )
    )
    gateway._sdk_client = client
    outcome, reason = await gateway._remote_evaluate(
        research_request(),
        {"mission_running": True},
    )
    assert outcome == "PERMIT" and "SDK policy" in reason
    assert client.session.closed


@pytest.mark.asyncio
async def test_live_sdk_session_reports_local_tool_execution():
    await create_schema()

    class Session:
        def __init__(self):
            self.reports = []
            self.closed = False

        def start_plan(self, tool_calls, goal):
            return SimpleNamespace(
                plan_id="plan-1", token_id="token-1", plan_hash="plan-hash"
            )

        def check(self, tool_name, arguments, user_email=None):
            return SimpleNamespace(
                allowed=True,
                action="allow",
                reason="allowed",
                matched_policy="local-tools",
                obligations=[],
            )

        def report(self, tool_name, arguments, result):
            self.reports.append((tool_name, arguments, result))

        def close(self):
            self.closed = True

    class Client:
        def __init__(self):
            self.session = Session()

        def start_session(self, options):
            return self.session

    gateway = ArmorIQGovernanceGateway(
        Settings(
            armoriq_mode="remote",
            armoriq_api_key="secret",
            _env_file=None,
        )
    )
    client = Client()
    gateway._sdk_client = client
    async with SessionLocal() as db:
        mission = Mission(objective="Exercise the SDK local-tool lifecycle")
        db.add(mission)
        await db.flush()
        action = research_request(mission_id=mission.id)
        permit = await gateway.authorize_tool_call(
            db,
            action,
            {"mission_running": True},
        )
        result = {"status": "executed"}
        await gateway.verify_execution(db, action, permit, result)

    assert permit.outcome == "PERMIT"
    assert client.session.reports == [("web_research", action.arguments, result)]
    assert client.session.closed
