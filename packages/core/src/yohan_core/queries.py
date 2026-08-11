"""Read models over the traces table.

Async query helpers shared by any process that needs to read history — the
dashboard API (Phase 5) is the first. They take an asyncpg pool and return plain
dicts. Writes live in ``traces.py``; this module is read-only.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg


async def _rows(pool: asyncpg.Pool, sql: str, *args: Any) -> list[dict]:
    async with pool.acquire() as conn:
        return [dict(r) for r in await conn.fetch(sql, *args)]


async def recent_traces(pool: asyncpg.Pool, limit: int = 50) -> list[dict]:
    """One row per command (trace), newest first — the history view."""
    return await _rows(
        pool,
        """
        SELECT
            trace_id,
            min(event_ts)                                            AS started_at,
            max(event_ts)                                            AS last_at,
            count(*)                                                 AS events,
            max(payload->>'text')  FILTER (WHERE event_type = 'command_received') AS command,
            max(payload->>'reply') FILTER (WHERE event_type = 'output_produced'
                                           AND payload->>'task_id' IS NULL)        AS reply,
            bool_or(event_type = 'task_completed')                   AS completed,
            bool_or(event_type IN ('task_failed', 'budget_exceeded')) AS errored
        FROM traces
        GROUP BY trace_id
        ORDER BY started_at DESC
        LIMIT $1
        """,
        limit,
    )


async def trace_events(pool: asyncpg.Pool, trace_id: str) -> list[dict]:
    """The full ordered event list for one trace — used to build the DAG."""
    return await _rows(
        pool,
        """
        SELECT id, event_ts, event_type, agent_id, payload
        FROM traces
        WHERE trace_id = $1
        ORDER BY id
        """,
        trace_id,
    )


async def pending_approvals(pool: asyncpg.Pool) -> list[dict]:
    """Approval requests with no decision yet — the action queue."""
    return await _rows(
        pool,
        """
        SELECT
            trace_id,
            payload->>'request_id'            AS request_id,
            payload->>'action'                AS action,
            payload->'detail'->'arguments'    AS arguments,
            event_ts
        FROM traces
        WHERE event_type = 'approval_requested'
          AND payload->>'request_id' NOT IN (
              SELECT payload->>'request_id'
              FROM traces
              WHERE event_type IN ('approval_granted', 'approval_denied')
          )
        ORDER BY event_ts DESC
        """,
    )


def coerce_json_fields(rows: list[dict], fields: tuple[str, ...]) -> list[dict]:
    """asyncpg returns jsonb sub-selects as str; decode named fields to objects."""
    for row in rows:
        for field in fields:
            value = row.get(field)
            if isinstance(value, str):
                try:
                    row[field] = json.loads(value)
                except (ValueError, TypeError):
                    pass
    return rows
