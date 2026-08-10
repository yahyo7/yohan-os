"""Exercise the bus loop without Telegram.

Publishes a command straight onto the echo stream, then reads the results stream
until the matching ``output_produced`` comes back and prints it. Run the echo
agent first (``scripts/run_echo.sh``), then this.

    uv run python scripts/smoke_echo.py "hello there"
"""

from __future__ import annotations

import asyncio
import sys

from yohan_core import Bus, Event, EventType, get_settings, new_trace_id


async def main(text: str) -> int:
    settings = get_settings()
    bus = Bus(settings)
    await bus.connect()
    try:
        trace_id = new_trace_id()
        await bus.publish(
            settings.agent_stream("echo"),
            Event(
                trace_id=trace_id,
                agent_id="smoke",
                event_type=EventType.COMMAND_RECEIVED,
                payload={"text": text, "reply_to": {"chat_id": 0, "message_id": 0}},
            ),
        )
        print(f"published command trace={trace_id!r} text={text!r}")

        # Read results with a throwaway group so we don't clash with the gateway.
        group = f"grp:smoke:{trace_id[-8:]}"
        async for message in bus.consume(
            settings.results_stream, group, "smoke", block_ms=2000
        ):
            evt = message.event
            await bus.ack(message, group)
            if evt.trace_id != trace_id:
                continue
            if evt.event_type is EventType.OUTPUT_PRODUCED:
                print(f"got reply: {evt.payload.get('reply')!r}")
                return 0
            if evt.event_type in (EventType.TASK_FAILED, EventType.BUDGET_EXCEEDED):
                print(f"agent reported {evt.event_type.value}: {evt.payload}")
                return 1
    finally:
        await bus.aclose()
    return 1


if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "hello"
    raise SystemExit(asyncio.run(main(text)))
