import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def uid() -> str:
    return str(uuid.uuid4())


class MissionStatus(str, enum.Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"


class AccountState(str, enum.Enum):
    DISCOVERED = "DISCOVERED"
    RESEARCHED = "RESEARCHED"
    EVIDENCE_VERIFIED = "EVIDENCE_VERIFIED"
    SCORED = "SCORED"
    CONTACTS_IDENTIFIED = "CONTACTS_IDENTIFIED"
    STRATEGY_DRAFTED = "STRATEGY_DRAFTED"
    OUTREACH_DRAFTED = "OUTREACH_DRAFTED"
    SENT = "SENT"
    REPLIED = "REPLIED"
    QUALIFIED = "QUALIFIED"
    MEETING_PROPOSED = "MEETING_PROPOSED"
    MEETING_BOOKED = "MEETING_BOOKED"
    MEETING_BRIEF_CREATED = "MEETING_BRIEF_CREATED"
    DISQUALIFIED = "DISQUALIFIED"
    POLICY_DENIED = "POLICY_DENIED"


class Mission(Base):
    __tablename__ = "missions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(
        String(200), default="Partner development mission"
    )
    objective: Mapped[str] = mapped_column(Text)
    status: Mapped[MissionStatus] = mapped_column(
        Enum(MissionStatus), default=MissionStatus.CREATED
    )
    policy: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    @property
    def progress(self) -> int:
        return (
            100
            if self.status == MissionStatus.COMPLETED
            else (50 if self.status == MissionStatus.RUNNING else 0)
        )

    @property
    def target_meetings(self) -> int:
        return int(self.policy.get("target_meetings", 0))

    @property
    def meetings_booked(self) -> int:
        return int(self.metrics.get("meetings", 0))

    @property
    def accounts_qualified(self) -> int:
        return int(self.metrics.get("qualified", self.metrics.get("meetings", 0)))


class PartnerAccount(Base):
    __tablename__ = "partner_accounts"
    __table_args__ = (UniqueConstraint("mission_id", "domain"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    domain: Mapped[str] = mapped_column(String(255))
    state: Mapped[AccountState] = mapped_column(
        Enum(AccountState), default=AccountState.DISCOVERED
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"), index=True)
    account_id: Mapped[str | None] = mapped_column(
        ForeignKey("partner_accounts.id"), nullable=True
    )
    agent: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30))
    input: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    trace_id: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class PolicyDecision(Base):
    __tablename__ = "policy_decisions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"), index=True)
    account_id: Mapped[str | None] = mapped_column(
        ForeignKey("partner_accounts.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    input_hash: Mapped[str] = mapped_column(String(64))
    permit_id: Mapped[str | None] = mapped_column(String, nullable=True)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"), index=True)
    kind: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    previous_hash: Mapped[str] = mapped_column(String(64), default="0" * 64)
    event_hash: Mapped[str] = mapped_column(String(64))
    sequence: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
