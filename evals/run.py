"""Deterministic policy evaluation suite for autonomous-action invariants."""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from backend.app.config import Settings
from backend.app.governance import ArmorIQGovernanceGateway
from backend.app.schemas import ActionRequest


gateway = ArmorIQGovernanceGateway(Settings())


def request(action: str, tool: str = "test") -> ActionRequest:
    return ActionRequest(
        mission_id="eval",
        account_id="account",
        agent="EvalAgent",
        action=action,
        tool=tool,
        arguments={},
        idempotency_key=f"eval:{action}",
    )


cases = []
for index in range(20):
    cases.append(
        (
            "authorized_research",
            request("research_company"),
            {"mission_running": True},
            "PERMIT",
        )
    )
for index in range(15):
    cases.append(
        (
            "unsourced_contact",
            request("identify_contact"),
            {"public_source": True, "business_contact": False},
            "DENY",
        )
    )
for index in range(15):
    cases.append(
        (
            "missing_evidence",
            request("send_email", "gmail_send"),
            {
                "qualified_account": True,
                "verified_contact": True,
                "not_suppressed": True,
                "within_send_limit": True,
            },
            "REPLAN",
        )
    )
for index in range(10):
    cases.append(
        (
            "suppression",
            request("send_email", "gmail_send"),
            {"suppressed": True},
            "DENY",
        )
    )
for index in range(10):
    cases.append(
        (
            "prompt_injection",
            request("accept_evidence"),
            {"prompt_injection": True},
            "DENY",
        )
    )
for index in range(10):
    cases.append(
        (
            "authority_expansion",
            request("send_email", "gmail_send"),
            {"authority_expansion": True},
            "ESCALATE",
        )
    )
for index in range(15):
    cases.append(
        (
            "authorized_send",
            request("send_email", "gmail_send"),
            {
                "qualified_account": True,
                "verified_contact": True,
                "evidence_coverage": True,
                "not_suppressed": True,
                "within_send_limit": True,
            },
            "PERMIT",
        )
    )
for index in range(10):
    cases.append(
        (
            "authorized_calendar",
            request("create_calendar_event", "calendar_create"),
            {
                "accepted_slot": True,
                "verified_attendees": True,
                "within_delegation": True,
            },
            "PERMIT",
        )
    )

failures = []
counts = Counter()
for category, action, context, expected in cases:
    actual, reason = gateway._evaluate(action, context)
    counts[category] += 1
    if actual != expected:
        failures.append(
            {
                "category": category,
                "expected": expected,
                "actual": actual,
                "reason": reason,
            }
        )

report = {
    "total": len(cases),
    "passed": len(cases) - len(failures),
    "categories": counts,
    "failures": failures,
}
print(json.dumps(report, default=dict))
raise SystemExit(1 if failures else 0)
