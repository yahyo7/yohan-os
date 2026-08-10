"""Read-only queries over the traces table.

Streamlit runs synchronously and reruns the whole script on every interaction,
so we open a short-lived asyncpg connection per query via ``asyncio.run``. That's
wasteful in principle but perfectly fine for a single-user MVP refreshing every
couple of seconds — and it keeps us on the one Postgres driver the rest of the
system uses, rather than pulling in a synchronous one just for the dashboard.
"""

from __future__ import annotations

import asyncio
from typing import Any

import asyncpg

from yohan_core import get_settings


async def _fetch(sql: str, *args: Any) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(get_settings().postgres_dsn)
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


def fetch(sql: str, *args: Any) -> list[dict]:
    """Run a query and return plain dicts (Streamlit/pandas-friendly)."""
    return [dict(r) for r in asyncio.run(_fetch(sql, *args))]


def event_type_counts() -> list[dict]:
    return fetch(
        """
        SELECT event_type, count(*) AS n
        FROM traces
        GROUP BY event_type
        ORDER BY n DESC
        """
    )


def totals() -> dict:
    rows = fetch(
        """
        SELECT
            count(*)                       AS events,
            count(DISTINCT trace_id)       AS traces,
            count(*) FILTER (WHERE event_type = 'task_failed')     AS failed,
            count(*) FILTER (WHERE event_type = 'budget_exceeded') AS budget_exceeded
        FROM traces
        """
    )
    return rows[0] if rows else {"events": 0, "traces": 0, "failed": 0, "budget_exceeded": 0}


def recent_traces(limit: int = 25) -> list[dict]:
    """One row per command, newest first: when it started, how far it got, the text."""
    return fetch(
        """
        SELECT
            trace_id,
            min(event_ts)                                            AS started_at,
            count(*)                                                 AS events,
            max(event_ts)                                            AS last_at,
            -- the command text (from command_received) and reply (from output_produced)
            max(payload->>'text')  FILTER (WHERE event_type = 'command_received') AS command,
            max(payload->>'reply') FILTER (WHERE event_type = 'output_produced')  AS reply,
            bool_or(event_type = 'task_completed')                   AS completed,
            bool_or(event_type IN ('task_failed', 'budget_exceeded')) AS errored
        FROM traces
        GROUP BY trace_id
        ORDER BY started_at DESC
        LIMIT $1
        """,
        limit,
    )


def events_for_trace(trace_id: str) -> list[dict]:
    """The full ordered event timeline for one command."""
    return fetch(
        """
        SELECT event_ts, event_type, agent_id, payload
        FROM traces
        WHERE trace_id = $1
        ORDER BY id
        """,
        trace_id,
    )
