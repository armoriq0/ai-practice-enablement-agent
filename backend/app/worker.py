import asyncio
import logging
import signal

from sqlalchemy import select

from .agents import SupervisorAgent
from .config import get_settings
from .db import SessionLocal, create_schema
from .governance import ArmorIQGovernanceGateway
from .models import Mission, MissionStatus
from .tools import DeterministicWorkspaceAdapter, GovernedToolGateway

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("partner-background-worker")


async def run_cycle() -> int:
    settings = get_settings()
    if not settings.autonomous_execution_enabled:
        logger.info("Autonomous execution is disabled; skipping cycle")
        return 0
    governance = ArmorIQGovernanceGateway(settings)
    supervisor = SupervisorAgent(
        governance,
        GovernedToolGateway(governance, DeterministicWorkspaceAdapter()),
        settings=settings,
    )
    async with SessionLocal() as db:
        missions = list(
            await db.scalars(
                select(Mission)
                .where(Mission.status.in_([MissionStatus.CREATED, MissionStatus.COMPLETED]))
                .order_by(Mission.created_at)
            )
        )
        missions = [
            m
            for m in missions
            if m.policy.get("auto_execute", False)
            and m.policy.get("continuous", False)
        ]
        for mission in missions:
            try:
                logger.info("Running recurring discovery for mission %s", mission.id)
                await supervisor.run(db, mission, [])
            except Exception:
                await db.rollback()
                logger.exception("Recurring mission failed: %s", mission.id)
        return len(missions)


async def main() -> None:
    await create_schema()
    settings = get_settings()
    if settings.background_worker_run_once:
        await run_cycle()
        return
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for value in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(value, stop.set)
    while not stop.is_set():
        await run_cycle()
        try:
            await asyncio.wait_for(
                stop.wait(), timeout=settings.background_worker_interval_seconds
            )
        except TimeoutError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
