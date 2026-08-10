"""The traces store — persist every bus event, idempotently.

One function to apply the schema, one to insert an event. Kept deliberately small:
the trace writer is "a single subscriber" (per the brief), and this is the only
write path into the source-of-truth table.

The insert is idempotent on ``(stream, entry_id)`` so at-least-once redelivery —
e.g. the writer crashing after persisting but before acking — never duplicates a
row. That property is what lets the bus stay at-least-once while the table stays
exactly-once.
"""

from __future__ import annotations

import json
from pathlib import Path

import asyncpg

from yohan_core.events import Event

# The DDL lives in infra/migrations and is applied on writer startup for dev
# ergonomics. Resolve it relative to the repo so we don't duplicate the schema.
_MIGRATION = (
    Path(__file__).resolve().parents[4]
    / "infra"
    / "migrations"
    / "001_traces.sql"
)


async def apply_schema(pool: asyncpg.Pool) -> None:
    """Create the traces table + indexes if they don't exist (idempotent)."""
    ddl = _MIGRATION.read_text()
    async with pool.acquire() as conn:
        await conn.execute(ddl)


async def insert_event(
    pool: asyncpg.Pool,
    event: Event,
    *,
    stream: str | None = None,
    entry_id: str | None = None,
) -> None:
    """Write one event to ``traces``. No-op if this stream entry is already stored."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO traces
                (trace_id, agent_id, event_type, event_ts, payload, stream, entry_id)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
            ON CONFLICT (stream, entry_id) DO NOTHING
            """,
            event.trace_id,
            event.agent_id,
            event.event_type.value,
            event.timestamp,
            json.dumps(event.payload),
            stream,
            entry_id,
        )
