"""The supervisor workflow.

    command → plan (list[Task]) → dispatch in parallel → aggregate → one reply

``plan`` is the seam that grows as agents are added. Today: a "morning routine"
fans out to the daily briefing (and, as they mature, email triage etc.); a
"fanout" keyword is a demo that dispatches parallel echo tasks; anything else is
passed to a single echo. Sub-tasks deliberately omit reply_to so only the
supervisor's aggregated result is relayed to the user.

Run as a process:  ``python -m yohan_agents.supervisor.agent``
"""

from __future__ import annotations

import asyncio
import logging

from yohan_core import Event, EventType, Task, configure_logging, dispatch

from yohan_agents.base import BaseAgent

logger = logging.getLogger(__name__)


def plan(text: str) -> list[Task]:
    """Turn a command into a plan of parallel tasks."""
    lowered = text.lower()
    if "fanout" in lowered:
        return [Task(agent_type="echo", payload={"text": f"part-{i}"}) for i in range(3)]
    if any(k in lowered for k in ("morning", "routine", "briefing", "daily")):
        # As more source agents land, add them here — they run in parallel.
        return [Task(agent_type="daily_briefing", payload={})]
    return [Task(agent_type="echo", payload={"text": text})]


class SupervisorAgent(BaseAgent):
    agent_type = "supervisor"

    async def handle(self, command: Event) -> dict:
        trace_id = command.trace_id
        reply_to = command.payload.get("reply_to", {})
        tasks = plan(command.payload.get("text", ""))

        await self._emit(
            trace_id,
            self._consumer,
            EventType.PLAN_CREATED,
            {"tasks": [{"agent_type": t.agent_type, "task_id": t.task_id} for t in tasks]},
        )
        logger.info("plan created", extra={"n_tasks": len(tasks)})

        results = await dispatch(
            self._bus,
            trace_id=trace_id,
            agent_id=self._consumer,
            tasks=tasks,
            timeout_s=max(self.budget.max_seconds - 5, 10),
        )

        parts: list[str] = []
        for task in tasks:
            event = results.get(task.task_id)
            if event is not None:
                parts.append(event.payload.get("reply", ""))
            else:
                parts.append(f"[{task.agent_type} did not complete in time]")
        reply = "\n\n".join(p for p in parts if p) or "No results."
        return {"reply": reply, "reply_to": reply_to}


def main() -> None:
    configure_logging("agent:supervisor")
    asyncio.run(SupervisorAgent().run())


if __name__ == "__main__":
    main()
