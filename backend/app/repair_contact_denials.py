import asyncio
import os

from sqlalchemy import select

from .audit import append_audit
from .db import SessionLocal, create_schema
from .models import AccountState, Mission, MissionStatus, PartnerAccount, PolicyDecision


async def repair() -> int:
    mission_id = os.environ.get("MISSION_ID")
    if not mission_id:
        raise RuntimeError("MISSION_ID is required")
    await create_schema()
    async with SessionLocal() as db:
        mission = await db.get(Mission, mission_id)
        if not mission:
            raise RuntimeError(f"Mission not found: {mission_id}")
        matched_accounts = list(
            await db.scalars(
                select(PartnerAccount)
                .join(
                    PolicyDecision,
                    PolicyDecision.account_id == PartnerAccount.id,
                )
                .where(
                    PartnerAccount.mission_id == mission_id,
                    PartnerAccount.state == AccountState.POLICY_DENIED,
                    PolicyDecision.action == "identify_contact",
                    PolicyDecision.outcome == "DENY",
                    PolicyDecision.reason
                    == "Missing policy conditions: business_contact",
                )
            )
        )
        accounts = list({account.id: account for account in matched_accounts}.values())
        for account in accounts:
            account.state = AccountState.SCORED
        if accounts:
            mission.status = MissionStatus.PAUSED
            await append_audit(
                db,
                mission.id,
                "policy_repair.contact_discovery",
                {"accounts_reset": len(accounts), "from": "POLICY_DENIED", "to": "SCORED"},
            )
        await db.commit()
        return len(accounts)


async def main() -> None:
    repaired = await repair()
    print(f"Repaired {repaired} legacy contact-policy denials")


if __name__ == "__main__":
    asyncio.run(main())
