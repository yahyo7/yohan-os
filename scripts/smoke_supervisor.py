"""Drive the supervisor via the bus and print its aggregated reply.

Start supervisor + the agents its plan needs (echo, daily_briefing), then run:

    uv run python scripts/smoke_supervisor.py "fanout"
    uv run python scripts/smoke_supervisor.py "morning briefing"
"""

from __future__ import annotations

import asyncio
import sys

from yohan_core import Bus, Event, EventType, get_settings, new_trace_id


async def main(text: str) -> int:
    bus = Bus()
    await bus.connect()
    try:
        trace_id = new_trace_id()
        got: dict = {}

        async def collect() -> None:
            async for message in bus.tail(
                get_settings().results_stream, start="$", block_ms=2000
            ):
                ev = message.event
                # The supervisor's own top-level result carries no task_id
                # (sub-task outputs do), so this picks the aggregated reply.
                if (
                    ev.trace_id == trace_id
                    and ev.event_type is EventType.OUTPUT_PRODUCED
                    and "task_id" not in ev.payload
                ):
                    got["reply"] = ev.payload.get("reply")
                    return

        collector = asyncio.create_task(collect())
        await asyncio.sleep(0.2)
        await bus.publish(
            get_settings().agent_stream("supervisor"),
            Event(
                trace_id=trace_id,
                agent_id="smoke",
                event_type=EventType.COMMAND_RECEIVED,
                payload={"text": text, "reply_to": {"chat_id": 1, "message_id": 1}},
            ),
        )
        await asyncio.wait_for(collector, timeout=20)
        print(f"supervisor reply:\n{got.get('reply', '(none)')}")
        return 0 if got.get("reply") else 1
    finally:
        await bus.aclose()


if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "fanout"
    raise SystemExit(asyncio.run(main(text)))
