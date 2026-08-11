"""The scheduler loop.

Every tick it asks, per job: has a cron boundary passed since we last fired? If
so, publish the job's command onto its agent's stream (minting a fresh trace_id
and mirroring command_received to results, exactly like the gateway). On startup
we seed each job's "last fired" to now, so restarting doesn't replay the day's
past-due jobs.

Run as a process:  ``python -m yohan_scheduler.scheduler``
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from croniter import croniter

from yohan_core import Bus, Event, EventType, bind_trace_id, configure_logging, new_trace_id

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path(__file__).resolve().parents[4] / "infra" / "schedules.yaml"
_TICK_SECONDS = 20


@dataclass(frozen=True, slots=True)
class Job:
    name: str
    cron: str
    tz: str
    agent: str
    text: str
    chat_id: int


def load_jobs(path: Path | str | None = None) -> list[Job]:
    data = yaml.safe_load(Path(path or _DEFAULT_PATH).read_text()) or {}
    jobs = []
    for j in data.get("jobs", []) or []:
        jobs.append(
            Job(
                name=j["name"],
                cron=j["cron"],
                tz=j.get("tz", "UTC"),
                agent=j["agent"],
                text=j.get("text", ""),
                chat_id=int(j.get("chat_id", 0)),
            )
        )
    return jobs


def due_fire_time(cron: str, now: datetime, last_fired: datetime) -> datetime | None:
    """Most recent cron boundary <= now, if it's newer than last_fired; else None.

    Pure function of its inputs so the fire decision is unit-testable without a
    clock or a bus.
    """
    prev = croniter(cron, now).get_prev(datetime)
    return prev if prev > last_fired else None


async def fire(bus: Bus, job: Job) -> str:
    """Publish the job's command onto its agent's stream. Returns the trace_id."""
    from yohan_core import get_settings

    settings = get_settings()
    trace_id = new_trace_id()
    with bind_trace_id(trace_id):
        command = Event(
            trace_id=trace_id,
            agent_id="scheduler",
            event_type=EventType.COMMAND_RECEIVED,
            payload={
                "text": job.text,
                "channel": "scheduler",
                "reply_to": {"chat_id": job.chat_id} if job.chat_id else {},
            },
        )
        await bus.publish(settings.agent_stream(job.agent), command)
        await bus.publish_result(command)  # mirror for the trace writer
        logger.info("fired job %s → %s", job.name, job.agent, extra={"job": job.name})
    return trace_id


async def run() -> None:
    jobs = load_jobs()
    bus = Bus()
    await bus.connect()
    # Seed last-fired to now so we don't replay today's earlier boundaries.
    last: dict[str, datetime] = {
        job.name: datetime.now(ZoneInfo(job.tz)) for job in jobs
    }
    logger.info("scheduler up with %d job(s)", len(jobs))
    try:
        while True:
            for job in jobs:
                now = datetime.now(ZoneInfo(job.tz))
                fire_time = due_fire_time(job.cron, now, last[job.name])
                if fire_time is not None:
                    await fire(bus, job)
                    last[job.name] = fire_time
            await asyncio.sleep(_TICK_SECONDS)
    finally:
        await bus.aclose()


def main() -> None:
    configure_logging("scheduler")
    asyncio.run(run())


if __name__ == "__main__":
    main()
