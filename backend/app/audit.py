import hashlib
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AuditEvent


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


async def append_audit(
    db: AsyncSession, mission_id: str, kind: str, payload: dict
) -> AuditEvent:
    previous = await db.scalar(
        select(AuditEvent)
        .where(AuditEvent.mission_id == mission_id)
        .order_by(AuditEvent.sequence.desc())
        .limit(1)
    )
    sequence = (previous.sequence + 1) if previous else 1
    previous_hash = previous.event_hash if previous else "0" * 64
    event_hash = hashlib.sha256(
        f"{previous_hash}:{sequence}:{kind}:{canonical(payload)}".encode()
    ).hexdigest()
    event = AuditEvent(
        mission_id=mission_id,
        kind=kind,
        payload=payload,
        previous_hash=previous_hash,
        event_hash=event_hash,
        sequence=sequence,
    )
    db.add(event)
    return event


async def verify_chain(db: AsyncSession, mission_id: str) -> tuple[bool, int]:
    events = list(
        (
            await db.scalars(
                select(AuditEvent)
                .where(AuditEvent.mission_id == mission_id)
                .order_by(AuditEvent.sequence)
            )
        ).all()
    )
    previous_hash = "0" * 64
    for index, event in enumerate(events, 1):
        expected = hashlib.sha256(
            f"{previous_hash}:{index}:{event.kind}:{canonical(event.payload)}".encode()
        ).hexdigest()
        if (
            event.sequence != index
            or event.previous_hash != previous_hash
            or event.event_hash != expected
        ):
            return False, len(events)
        previous_hash = event.event_hash
    return True, len(events)
