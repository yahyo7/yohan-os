"""Approval gates as bus events.

The brief's rule: approval is per-tool, enforced at the tool layer, and approval
gates are *events on the bus*, not in-process calls. This module is the bus-native
mechanism both halves use.

* An agent about to run a side-effectful tool calls :func:`request_and_wait`:
  it emits ``approval_requested`` onto the results stream (where the dashboard and
  gateway see it) and parks until a matching decision arrives.
* An approver — the gateway (Telegram button) or the dashboard — calls
  :func:`publish_decision`, emitting ``approval_granted`` / ``approval_denied``
  onto the approvals stream, keyed by ``request_id``.

Decisions ride their own stream read with :meth:`Bus.tail` (broadcast), so many
agents can wait at once and each sees every decision, matching on its own
``request_id``.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from yohan_core.bus import Bus
from yohan_core.events import Event, EventType
from yohan_core.settings import get_settings


def new_request_id() -> str:
    """A short id correlating an approval request with its decision."""
    return f"apr_{uuid.uuid4().hex[:12]}"


@dataclass(slots=True)
class Decision:
    request_id: str
    granted: bool
    decided_by: str


async def request_approval(
    bus: Bus,
    *,
    trace_id: str,
    agent_id: str,
    action: str,
    detail: dict,
    request_id: str,
    reply_to: dict | None = None,
) -> None:
    """Emit ``approval_requested`` onto the results stream.

    ``action`` is a short human label (e.g. ``"gmail.send"``); ``detail`` carries
    what the approver needs to see (recipient, subject, body preview). ``reply_to``
    is threaded through so the gateway knows which Telegram chat to prompt.
    """
    await bus.publish_result(
        Event(
            trace_id=trace_id,
            agent_id=agent_id,
            event_type=EventType.APPROVAL_REQUESTED,
            payload={
                "request_id": request_id,
                "action": action,
                "detail": detail,
                "reply_to": reply_to or {},
            },
        )
    )


async def wait_for_decision(
    bus: Bus, request_id: str, *, timeout_s: float = 300.0
) -> Decision:
    """Park until a decision for ``request_id`` arrives, or time out."""
    approvals_stream = get_settings().approvals_stream

    async def _watch() -> Decision:
        async for message in bus.tail(approvals_stream, start="$", block_ms=2000):
            event = message.event
            if event.payload.get("request_id") != request_id:
                continue
            if event.event_type is EventType.APPROVAL_GRANTED:
                return Decision(request_id, True, event.payload.get("decided_by", ""))
            if event.event_type is EventType.APPROVAL_DENIED:
                return Decision(request_id, False, event.payload.get("decided_by", ""))
        raise AssertionError("unreachable: tail() never ends")

    return await asyncio.wait_for(_watch(), timeout=timeout_s)


async def request_and_wait(
    bus: Bus,
    *,
    trace_id: str,
    agent_id: str,
    action: str,
    detail: dict,
    reply_to: dict | None = None,
    timeout_s: float = 300.0,
) -> Decision:
    """Request approval and block until decided. Raises ``TimeoutError`` on lapse.

    We start tailing the approvals stream *before* publishing the request, so a
    fast decision can't slip in between publish and wait. (Human approvals are
    slow, but correctness shouldn't rely on that.)
    """
    request_id = new_request_id()
    waiter = asyncio.create_task(
        wait_for_decision(bus, request_id, timeout_s=timeout_s)
    )
    await asyncio.sleep(0)  # let the waiter issue its first XREAD before we publish
    await request_approval(
        bus,
        trace_id=trace_id,
        agent_id=agent_id,
        action=action,
        detail=detail,
        request_id=request_id,
        reply_to=reply_to,
    )
    return await waiter


async def publish_decision(
    bus: Bus,
    *,
    request_id: str,
    trace_id: str,
    granted: bool,
    decided_by: str,
) -> None:
    """Emit a decision onto the approvals stream (called by gateway / dashboard).

    Also mirrored onto the results stream so the trace writer persists it and the
    dashboard can tell which requests are still pending — same pattern as the
    gateway mirroring command_received. The waiting agent reads the approvals
    stream; tracing/observers read results.
    """
    event_type = EventType.APPROVAL_GRANTED if granted else EventType.APPROVAL_DENIED
    event = Event(
        trace_id=trace_id,
        agent_id=decided_by,
        event_type=event_type,
        payload={"request_id": request_id, "decided_by": decided_by, "granted": granted},
    )
    await bus.publish(get_settings().approvals_stream, event)
    await bus.publish_result(event)
