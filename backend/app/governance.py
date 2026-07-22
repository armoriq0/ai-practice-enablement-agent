import asyncio
import base64
import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from armoriq_sdk import (  # type: ignore[import-untyped]
    ArmorIQClient,
    ArmorIQException,
    ArmorIQSession,
    SessionOptions,
)
import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from .audit import append_audit, canonical
from .config import Settings, get_settings
from .models import PolicyDecision
from .schemas import ActionRequest, Permit


class ArmorIQGovernanceGateway:
    """Application adapter for ArmorIQ. Local mode is a strict policy engine, not a bypass.

    The interface mirrors the intended SDK concepts so a remote SDK adapter can replace
    `_evaluate` without changing agents or tool gateways.
    """

    def __init__(
        self, settings: Settings | None = None, policy_path: Path | None = None
    ):
        self.settings = settings or get_settings()
        path = policy_path or Path(__file__).parents[2] / "policies" / "autonomy.yaml"
        self.policy = yaml.safe_load(path.read_text())
        self._sdk_client: ArmorIQClient | None = None
        self._sdk_sessions: dict[str, ArmorIQSession] = {}

    @staticmethod
    def input_hash(request: ActionRequest) -> str:
        bound = request.model_dump(exclude={"idempotency_key"})
        return hashlib.sha256(canonical(bound).encode()).hexdigest()

    async def capture_purpose(
        self, db: AsyncSession, mission_id: str, purpose: str
    ) -> None:
        await append_audit(db, mission_id, "purpose.captured", {"purpose": purpose})

    async def capture_plan(
        self, db: AsyncSession, mission_id: str, plan: list[str]
    ) -> str:
        commitment = hashlib.sha256(canonical(plan).encode()).hexdigest()
        await append_audit(
            db, mission_id, "plan.committed", {"steps": plan, "commitment": commitment}
        )
        return commitment

    def _evaluate(
        self, request: ActionRequest, context: dict[str, Any]
    ) -> tuple[Literal["PERMIT", "DENY", "REPLAN", "ESCALATE"], str]:
        rule = self.policy["actions"].get(request.action)
        if not rule:
            return "DENY", "Action is absent from the delegated policy"
        if context.get("authority_expansion") or context.get("sensitive_recipient"):
            return "ESCALATE", "Action requires authority outside the mission envelope"
        if context.get("prompt_injection") or context.get("suppressed"):
            return "DENY", "Unsafe evidence or suppressed recipient"
        missing = [
            requirement
            for requirement in rule.get("requirements", [])
            if not context.get(requirement, False)
        ]
        if missing:
            replan = {
                "verified_evidence",
                "evidence_coverage",
                "accepted_slot",
            }.intersection(missing)
            return (
                "REPLAN" if replan else "DENY"
            ), f"Missing policy conditions: {', '.join(missing)}"
        return (
            "PERMIT",
            "Action is within delegated purpose, plan, evidence, and limits",
        )

    def _get_sdk_client(self) -> ArmorIQClient:
        if not self.settings.armoriq_api_key:
            raise RuntimeError("ARMORIQ_API_KEY is required in live ArmorIQ mode")
        if self._sdk_client is None:
            kwargs: dict[str, Any] = {
                "api_key": self.settings.armoriq_api_key,
                "user_id": self.settings.armoriq_user_id,
                "agent_id": self.settings.armoriq_agent_id,
                "timeout": 15.0,
                "max_retries": 2,
                "use_production": True,
            }
            if self.settings.armoriq_base_url:
                kwargs["backend_endpoint"] = self.settings.armoriq_base_url.rstrip("/")
            self._sdk_client = ArmorIQClient(**kwargs)
        return self._sdk_client

    def _sdk_authorize_sync(
        self, request: ActionRequest, context: dict[str, Any]
    ) -> tuple[
        Literal["PERMIT", "DENY", "REPLAN", "ESCALATE"],
        str,
        ArmorIQSession | None,
        dict[str, Any],
    ]:
        local_outcome, local_reason = self._evaluate(request, context)
        if local_outcome != "PERMIT":
            return local_outcome, local_reason, None, {}

        client = self._get_sdk_client()
        options = SessionOptions(
            mode="sdk",
            default_mcp_name=self.settings.armoriq_local_tool_namespace,
            validity_seconds=self.settings.permit_ttl_seconds,
            llm=self.settings.openai_model,
        )
        session = (
            client.for_user(self.settings.armoriq_operator_email).start_session(options)
            if self.settings.armoriq_operator_email
            else client.start_session(options)
        )
        try:
            token = session.start_plan(
                [{"name": request.tool, "args": request.arguments}],
                goal=f"{request.agent}: {request.action}",
            )
            decision = session.check(
                request.tool,
                request.arguments,
                user_email=self.settings.armoriq_operator_email,
            )
            metadata = {
                "armoriq_plan_id": token.plan_id,
                "armoriq_token_id": token.token_id,
                "armoriq_plan_hash": token.plan_hash,
                "armoriq_matched_policy": decision.matched_policy,
                "armoriq_obligations": decision.obligations,
            }
            if decision.allowed and decision.action == "allow":
                return (
                    "PERMIT",
                    decision.reason
                    or "ArmorIQ SDK permitted the plan-bound local tool",
                    session,
                    metadata,
                )
            session.close()
            outcome: Literal["DENY", "ESCALATE"] = (
                "ESCALATE" if decision.action == "hold" else "DENY"
            )
            return (
                outcome,
                decision.reason or f"ArmorIQ SDK returned {decision.action}",
                None,
                metadata,
            )
        except (ArmorIQException, RuntimeError, ValueError, TypeError) as exc:
            session.close()
            if self.settings.armoriq_fail_closed:
                return (
                    "DENY",
                    f"Live ArmorIQ SDK authorization failed closed: {type(exc).__name__}",
                    None,
                    {},
                )
            raise

    async def _remote_evaluate(
        self, request: ActionRequest, context: dict[str, Any]
    ) -> tuple[Literal["PERMIT", "DENY", "REPLAN", "ESCALATE"], str]:
        if not self.settings.armoriq_api_key:
            return "DENY", "Live ArmorIQ is required but not configured"
        outcome, reason, session, _ = await asyncio.to_thread(
            self._sdk_authorize_sync, request, context
        )
        if session:
            session.close()
        return outcome, reason

    async def authorize_tool_call(
        self, db: AsyncSession, request: ActionRequest, context: dict[str, Any]
    ) -> Permit:
        sdk_session: ArmorIQSession | None = None
        sdk_metadata: dict[str, Any] = {}
        outcome: Literal["PERMIT", "DENY", "REPLAN", "ESCALATE"]
        reason: str
        if self.settings.armoriq_mode.lower() not in {"local", "mock"}:
            if not self.settings.armoriq_api_key:
                outcome, reason = (
                    "DENY",
                    "Live ArmorIQ is required but not configured",
                )
            else:
                outcome, reason, sdk_session, sdk_metadata = await asyncio.to_thread(
                    self._sdk_authorize_sync, request, context
                )
        else:
            outcome, reason = self._evaluate(request, context)
        digest = self.input_hash(request)
        permit_id = str(uuid.uuid4())
        expires = (
            datetime.now(UTC) + timedelta(seconds=self.settings.permit_ttl_seconds)
            if outcome == "PERMIT"
            else None
        )
        token = None
        if expires:
            claims = {
                "permit_id": permit_id,
                "input_hash": digest,
                "action": request.action,
                "tool": request.tool,
                "agent": request.agent,
                "exp": int(expires.timestamp()),
            }
            encoded = (
                base64.urlsafe_b64encode(canonical(claims).encode())
                .decode()
                .rstrip("=")
            )
            signature = hmac.new(
                self.settings.armoriq_signing_key.encode(),
                encoded.encode(),
                hashlib.sha256,
            ).hexdigest()
            token = f"{encoded}.{signature}"
        decision_context = {
            **context,
            "agent": request.agent,
            "tool": request.tool,
            "risk": request.risk,
            **sdk_metadata,
        }
        db.add(
            PolicyDecision(
                mission_id=request.mission_id,
                account_id=request.account_id,
                action=request.action,
                outcome=outcome,
                reason=reason,
                input_hash=digest,
                permit_id=permit_id if token else None,
                context=decision_context,
            )
        )
        await append_audit(
            db,
            request.mission_id,
            "policy.decision",
            {
                "permit_id": permit_id,
                "outcome": outcome,
                "action": request.action,
                "input_hash": digest,
                "reason": reason,
            },
        )
        permit = Permit(
            permit_id=permit_id,
            outcome=outcome,
            reason=reason,
            action=request.action,
            tool=request.tool,
            agent=request.agent,
            input_hash=digest,
            expires_at=expires,
            token=token,
        )
        if sdk_session and outcome == "PERMIT":
            self._sdk_sessions[permit_id] = sdk_session
        return permit

    def validate_permit(self, permit: Permit, request: ActionRequest) -> None:
        if permit.outcome != "PERMIT" or not permit.token:
            raise PermissionError(f"ArmorIQ did not permit action: {permit.reason}")
        encoded, supplied = permit.token.split(".", 1)
        expected = hmac.new(
            self.settings.armoriq_signing_key.encode(), encoded.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(supplied, expected):
            raise PermissionError("Invalid ArmorIQ permit signature")
        claims = json.loads(
            base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        )
        if (
            claims["input_hash"] != self.input_hash(request)
            or claims["permit_id"] != permit.permit_id
        ):
            raise PermissionError("ArmorIQ permit is not bound to this exact action")
        if claims["exp"] < int(datetime.now(UTC).timestamp()):
            raise PermissionError("ArmorIQ permit expired")

    async def verify_execution(
        self,
        db: AsyncSession,
        request: ActionRequest,
        permit: Permit,
        result: dict[str, Any],
    ) -> None:
        self.validate_permit(permit, request)
        sdk_session = self._sdk_sessions.pop(permit.permit_id, None)
        if sdk_session:
            try:
                await asyncio.to_thread(
                    sdk_session.report,
                    request.tool,
                    request.arguments,
                    result,
                )
            finally:
                sdk_session.close()
        await append_audit(
            db,
            request.mission_id,
            "execution.verified",
            {
                "permit_id": permit.permit_id,
                "input_hash": permit.input_hash,
                "result_hash": hashlib.sha256(canonical(result).encode()).hexdigest(),
            },
        )
