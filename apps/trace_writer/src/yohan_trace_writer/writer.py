"""The trace writer loop.

Consume the results stream as ``grp:tracewriter`` and write every event to the
traces table, then ack. Ordering matters: we persist *before* we ack, so a crash
between the two leaves the entry pending for redelivery and the idempotent insert
(unique on stream+entry_id) makes the retry harmless. That is how at-least-once
delivery on the bus becomes exactly-once rows in the table.

Run it as a process:  ``python -m yohan_trace_writer.writer``
"""

from __future__ import annotations

import asyncio
import logging

from yohan_core import Bus, Database, apply_schema, get_settings, insert_event

logger = logging.getLogger(__name__)

_GROUP = "grp:tracewriter"


async def run() -> None:
    settings = get_settings()
    bus = Bus(settings)
    db = Database(settings)
    await bus.connect()
    await db.connect()
    await apply_schema(db.pool)  # idempotent; makes a fresh DB usable immediately.

    logger.info("trace writer consuming %s -> traces", settings.results_stream)
    try:
        async for message in bus.consume(
            settings.results_stream, _GROUP, "trace-writer"
        ):
            # Persist first...
            await insert_event(
                db.pool,
                message.event,
                stream=message.stream,
                entry_id=message.entry_id,
            )
            # ...then ack. Crash in between => redelivery => idempotent no-op.
            await bus.ack(message, _GROUP)
    finally:
        await bus.aclose()
        await db.aclose()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
