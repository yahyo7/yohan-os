"""Parallel dispatch — fan work out to agents, gather results by task.

The supervisor uses this to run several agents at once. Each task is published to
its agent's stream as a command carrying a unique ``task_id``; the agents run
independently (they already consume their own streams), and this collects their
``output_produced`` events off the results stream, matching on ``task_id``.

The whole fan-out shares the parent command's ``trace_id`` — sub-work stays part
of one causal chain rather than fragmenting into child traces — with ``task_id``
distinguishing the branches. A ``task_assigned`` event is emitted per task so the
plan is visible in the trace.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field

from yohan_core.bus import Bus
from yohan_core.events import Event, EventType
from yohan_core.settings import get_settings


def new_task_id() -> str:
    return f"tsk_{uuid.uuid4().hex[:10]}"


@dataclass(slots=True)
class Task:
    agent_type: str
    payload: dict
    task_id: str = field(default_factory=new_task_id)


async def dispatch(
    bus: Bus,
    *,
    trace_id: str,
    agent_id: str,
    tasks: list[Task],
    timeout_s: float = 300.0,
) -> dict[str, Event]:
    """Publish tasks in parallel; return ``{task_id: output_produced event}``.

    Tasks that don't produce output before ``timeout_s`` are simply absent from
    the result — the caller decides how to handle a partial plan. We start
    collecting *before* publishing so no fast result is missed.
    """
    settings = get_settings()
    pending = {t.task_id for t in tasks}
    results: dict[str, Event] = {}

    if not tasks:
        return results

    async def _collect() -> None:
        async for message in bus.tail(settings.results_stream, start="$", block_ms=2000):
            event = message.event
            tid = event.payload.get("task_id")
            if tid not in pending:
                continue
            if event.event_type is EventType.OUTPUT_PRODUCED:
                results[tid] = event
                pending.discard(tid)
            elif event.event_type in (EventType.TASK_FAILED, EventType.BUDGET_EXCEEDED):
                # No output is coming for this task — stop waiting on it.
                pending.discard(tid)
            if not pending:
                return

    collector = asyncio.create_task(_collect())
    await asyncio.sleep(0)  # let the collector start tailing before we publish

    for task in tasks:
        command = Event(
            trace_id=trace_id,
            agent_id=agent_id,
            event_type=EventType.COMMAND_RECEIVED,
            payload={**task.payload, "task_id": task.task_id},
        )
        await bus.publish(settings.agent_stream(task.agent_type), command)
        await bus.publish_result(
            Event(
                trace_id=trace_id,
                agent_id=agent_id,
                event_type=EventType.TASK_ASSIGNED,
                payload={"task_id": task.task_id, "agent_type": task.agent_type},
            )
        )

    try:
        await asyncio.wait_for(collector, timeout=timeout_s)
    except asyncio.TimeoutError:
        collector.cancel()
    return results
