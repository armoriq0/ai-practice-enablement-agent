from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class MissionCreate(BaseModel):
    name: str = Field(
        default="Partner development mission", min_length=2, max_length=200
    )
    objective: str = Field(min_length=10, max_length=2000)
    target_meetings: int = Field(default=3, ge=1, le=100)
    max_outreach: int = Field(default=10, ge=1, le=1000)
    allowed_domains: list[str] = Field(default_factory=list)
    auto_execute: bool = True
    continuous: bool = True


class MissionView(BaseModel):
    id: str
    name: str
    objective: str
    status: str
    policy: dict[str, Any]
    metrics: dict[str, Any]
    progress: int
    target_meetings: int
    meetings_booked: int
    accounts_qualified: int
    created_at: datetime
    model_config = {"from_attributes": True}


class Candidate(BaseModel):
    name: str
    domain: str
    category: Literal[
        "ai_consulting",
        "cybersecurity",
        "systems_integration",
        "mssp",
        "cloud",
        "digital_engineering",
    ]
    public_business_email: str | None = None
    contact_source: str | None = None


class ActionRequest(BaseModel):
    mission_id: str
    account_id: str | None = None
    agent: str
    action: str
    tool: str
    arguments: dict[str, Any]
    evidence_ids: list[str] = Field(default_factory=list)
    idempotency_key: str
    risk: Literal["low", "medium", "high"] = "low"


class Permit(BaseModel):
    permit_id: str
    outcome: Literal["PERMIT", "DENY", "REPLAN", "ESCALATE"]
    reason: str
    action: str
    tool: str
    agent: str
    input_hash: str
    expires_at: datetime | None = None
    token: str | None = None
