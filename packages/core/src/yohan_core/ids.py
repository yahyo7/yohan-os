"""Identifier helpers.

`trace_id` is the single most important field in the system: it stitches together
every event, log line, and (from Phase 1) DB row that belongs to one command. We
generate it once, at the gateway, when a command first arrives, and then propagate
it unchanged through the whole causal chain.
"""

from __future__ import annotations

import uuid


def new_trace_id() -> str:
    """A fresh trace id for one inbound command. Minted at the gateway, only."""
    return f"trc_{uuid.uuid4().hex}"


def new_agent_id(agent_type: str) -> str:
    """A per-run id for a spawned agent instance, e.g. ``echo`` -> ``echo-1a2b3c4d``.

    Agents are spawn-on-demand (no long-lived workers in v1), so each run gets a
    distinct id. The ``agent_type`` prefix keeps traces human-readable.
    """
    return f"{agent_type}-{uuid.uuid4().hex[:8]}"
