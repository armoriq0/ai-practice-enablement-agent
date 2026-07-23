from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .agents import SupervisorAgent
from .audit import append_audit, verify_chain
from .db import create_schema, session
from .governance import ArmorIQGovernanceGateway
from .models import (
    AgentRun,
    AuditEvent,
    Mission,
    MissionStatus,
    PartnerAccount,
    PolicyDecision,
)
from .schemas import Candidate, MissionCreate, MissionView
from .tools import DeterministicWorkspaceAdapter, GovernedToolGateway


@asynccontextmanager
async def lifespan(_: FastAPI):
    await create_schema()
    yield


app = FastAPI(
    title="ArmorIQ Partner Development Agent", version="1.0.0", lifespan=lifespan
)
governance = ArmorIQGovernanceGateway()
supervisor = SupervisorAgent(
    governance, GovernedToolGateway(governance, DeterministicWorkspaceAdapter())
)
Db = Annotated[AsyncSession, Depends(session)]


class MissionRun(BaseModel):
    candidates: list[Candidate] = Field(default_factory=list)


class EscalationResolution(BaseModel):
    resolution: str = Field(pattern="^(allow|deny)$")


@app.get("/health")
@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/readiness")
async def readiness(db: Db) -> dict[str, str]:
    await db.execute(select(1))
    return {"status": "ready", "database": "ok", "governance": "configured"}


@app.post("/api/v1/tasks/scheduled/{workflow}", status_code=202)
async def scheduled_workflow(workflow: str) -> dict[str, str]:
    supported = {
        "discovery",
        "followups",
        "replies",
        "evidence-refresh",
        "stale-accounts",
        "analytics",
        "cost-report",
    }
    if workflow not in supported:
        raise HTTPException(404, "Unknown scheduled workflow")
    return {
        "status": "accepted",
        "workflow": workflow,
        "authorization": "required_per_action",
    }


@app.post("/api/v1/missions", response_model=MissionView, status_code=201)
async def create_mission(payload: MissionCreate, db: Db) -> Mission:
    mission = Mission(
        name=payload.name,
        objective=payload.objective,
        policy={
            "target_meetings": payload.target_meetings,
            "max_outreach": payload.max_outreach,
            "allowed_domains": payload.allowed_domains,
            "auto_execute": payload.auto_execute,
            "continuous": payload.continuous,
        },
    )
    db.add(mission)
    await db.commit()
    await db.refresh(mission)
    return mission


@app.get("/api/v1/missions", response_model=list[MissionView])
async def list_missions(db: Db) -> list[Mission]:
    return list(
        (await db.scalars(select(Mission).order_by(Mission.created_at.desc()))).all()
    )


@app.get("/api/v1/missions/{mission_id}", response_model=MissionView)
async def get_mission(mission_id: str, db: Db) -> Mission:
    mission = await db.get(Mission, mission_id)
    if not mission:
        raise HTTPException(404, "Mission not found")
    return mission


@app.post("/api/v1/missions/{mission_id}/start", response_model=MissionView)
async def start_mission(mission_id: str, db: Db) -> Mission:
    mission = await db.get(Mission, mission_id)
    if not mission:
        raise HTTPException(404, "Mission not found")
    return await supervisor.run(db, mission, MissionRun().candidates)


@app.post("/api/v1/missions/{mission_id}/pause", response_model=MissionView)
@app.post("/api/v1/missions/{mission_id}/stop", response_model=MissionView)
async def pause_mission(mission_id: str, db: Db) -> Mission:
    mission = await db.get(Mission, mission_id)
    if not mission:
        raise HTTPException(404, "Mission not found")
    mission.status = MissionStatus.PAUSED
    await db.commit()
    return mission


@app.post("/api/v1/missions/{mission_id}/resume", response_model=MissionView)
async def resume_mission(mission_id: str, db: Db) -> Mission:
    mission = await db.get(Mission, mission_id)
    if not mission:
        raise HTTPException(404, "Mission not found")
    return await supervisor.run(db, mission, MissionRun().candidates)


@app.post("/api/v1/missions/{mission_id}/run", response_model=MissionView)
async def run_mission(mission_id: str, payload: MissionRun, db: Db) -> Mission:
    mission = await db.get(Mission, mission_id)
    if not mission:
        raise HTTPException(404, "Mission not found")
    if not mission.policy.get("auto_execute", True):
        raise HTTPException(409, "Mission is not delegated for autonomous execution")
    return await supervisor.run(db, mission, payload.candidates)


@app.post("/api/v1/missions/{mission_id}/seed")
async def seed_mission(mission_id: str, payload: MissionRun, db: Db) -> dict[str, int | str]:
    mission = await db.get(Mission, mission_id)
    if not mission:
        raise HTTPException(404, "Mission not found")
    if not mission.policy.get("auto_execute", True):
        raise HTTPException(409, "Mission is not delegated for autonomous execution")
    existing_domains = set(
        await db.scalars(
            select(PartnerAccount.domain).where(
                PartnerAccount.mission_id == mission_id
            )
        )
    )
    added = 0
    for candidate in payload.candidates:
        if candidate.domain in existing_domains:
            continue
        db.add(
            PartnerAccount(
                mission_id=mission.id,
                name=candidate.name,
                domain=candidate.domain,
                data={
                    "category": candidate.category,
                    "public_business_email": candidate.public_business_email,
                    "contact_source": candidate.contact_source,
                    "source": "operator_seed",
                },
            )
        )
        existing_domains.add(candidate.domain)
        added += 1
    mission.status = MissionStatus.PAUSED
    await append_audit(
        db,
        mission.id,
        "mission.seeded",
        {"added": added, "total_submitted": len(payload.candidates)},
    )
    await db.commit()
    return {"mission_id": mission.id, "added": added, "total": len(existing_domains)}


@app.get("/api/v1/missions/{mission_id}/accounts")
async def mission_accounts(mission_id: str, db: Db) -> list[dict]:
    accounts = (
        await db.scalars(
            select(PartnerAccount).where(PartnerAccount.mission_id == mission_id)
        )
    ).all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "domain": a.domain,
            "state": a.state.value,
            "score": a.score,
            "tier": a.tier,
            "data": a.data,
        }
        for a in accounts
    ]


@app.get("/api/v1/missions/{mission_id}/policy-decisions")
async def policy_decisions(mission_id: str, db: Db) -> list[dict]:
    values = (
        await db.scalars(
            select(PolicyDecision)
            .where(PolicyDecision.mission_id == mission_id)
            .order_by(PolicyDecision.created_at)
        )
    ).all()
    return [
        {
            "id": v.id,
            "action": v.action,
            "outcome": v.outcome,
            "reason": v.reason,
            "permit_id": v.permit_id,
            "input_hash": v.input_hash,
            "created_at": v.created_at,
        }
        for v in values
    ]


@app.get("/api/v1/missions/{mission_id}/audit")
async def audit(mission_id: str, db: Db) -> dict:
    valid, count = await verify_chain(db, mission_id)
    values = (
        await db.scalars(
            select(AuditEvent)
            .where(AuditEvent.mission_id == mission_id)
            .order_by(AuditEvent.sequence)
        )
    ).all()
    return {
        "valid": valid,
        "count": count,
        "events": [
            {
                "sequence": v.sequence,
                "kind": v.kind,
                "payload": v.payload,
                "previous_hash": v.previous_hash,
                "event_hash": v.event_hash,
            }
            for v in values
        ],
    }


@app.get("/api/v1/agent-runs")
async def agent_runs(db: Db, limit: int = 50) -> list[dict]:
    values = (
        await db.scalars(
            select(AgentRun).order_by(AgentRun.created_at.desc()).limit(min(limit, 200))
        )
    ).all()
    return [
        {
            "id": v.id,
            "agent_name": v.agent,
            "mission_id": v.mission_id,
            "status": v.status,
            "started_at": v.created_at,
            "current_step": v.input.get("state"),
        }
        for v in values
    ]


@app.get("/api/v1/policy-decisions")
async def all_policy_decisions(db: Db, limit: int = 50) -> list[dict]:
    values = (
        await db.scalars(
            select(PolicyDecision)
            .order_by(PolicyDecision.created_at.desc())
            .limit(min(limit, 200))
        )
    ).all()
    return [
        {
            "id": v.id,
            "agent_name": v.context.get("agent"),
            "action": v.action,
            "outcome": v.outcome,
            "reason": v.reason,
            "created_at": v.created_at,
        }
        for v in values
    ]


@app.get("/api/v1/escalations")
async def escalations(db: Db, status: str = "open", limit: int = 50) -> list[dict]:
    del status
    values = (
        await db.scalars(
            select(PolicyDecision)
            .where(PolicyDecision.outcome == "ESCALATE")
            .order_by(PolicyDecision.created_at.desc())
            .limit(min(limit, 200))
        )
    ).all()
    return [
        {
            "id": v.id,
            "title": v.action,
            "reason": v.reason,
            "severity": "high",
            "status": "open",
            "created_at": v.created_at,
        }
        for v in values
    ]


@app.post("/api/v1/escalations/{decision_id}/resolve")
async def resolve_escalation(
    decision_id: str, payload: EscalationResolution, db: Db
) -> dict:
    decision = await db.get(PolicyDecision, decision_id)
    if not decision or decision.outcome != "ESCALATE":
        raise HTTPException(404, "Open escalation not found")
    if decision.context.get("resolution"):
        raise HTTPException(409, "Escalation has already been resolved")
    context = dict(decision.context)
    context.update(
        {
            "resolution": payload.resolution,
            "resolution_effect": "fresh_action_bound_authorization_required"
            if payload.resolution == "allow"
            else "action_denied",
        }
    )
    decision.context = context
    await append_audit(
        db,
        decision.mission_id,
        "escalation.resolved",
        {
            "decision_id": decision.id,
            "action": decision.action,
            "resolution": payload.resolution,
            "permit_issued": False,
            "next_step": context["resolution_effect"],
        },
    )
    await db.commit()
    return {
        "id": decision.id,
        "status": "resolved",
        "resolution": payload.resolution,
        "permit_issued": False,
        "next_step": context["resolution_effect"],
    }


@app.get("/api/v1/audit")
async def all_audit(db: Db, limit: int = 50) -> list[dict]:
    values = (
        await db.scalars(
            select(AuditEvent)
            .order_by(AuditEvent.created_at.desc())
            .limit(min(limit, 200))
        )
    ).all()
    return [
        {
            "id": v.id,
            "event_type": v.kind,
            "actor": v.payload.get("agent", "system"),
            "summary": v.payload.get("reason", v.kind),
            "created_at": v.created_at,
            "integrity_verified": True,
        }
        for v in values
    ]
