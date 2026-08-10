"""The event schema — the contract every process agrees on.

Every event on the bus carries: ``trace_id``, ``agent_id``, ``event_type``,
``timestamp``, ``payload``. That is the whole wire format. Agents communicate
*only* by publishing and consuming these — never by calling each other.

From Phase 1, a single subscriber writes every event to the Postgres ``traces``
table, which becomes the source of truth for the dashboard and for replay. That
is why the model is strict and fully serializable: what goes on the wire is
exactly what gets persisted.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from yohan_core.ids import new_agent_id  # noqa: F401  (re-exported convenience)


class EventType(str, Enum):
    """The closed set of event types. Str-valued so they serialize as plain text."""

    # Lifecycle of a command flowing through the system.
    COMMAND_RECEIVED = "command_received"
    PLAN_CREATED = "plan_created"
    TASK_ASSIGNED = "task_assigned"
    TASK_STARTED = "task_started"
    TOOL_CALLED = "tool_called"
    TOOL_RETURNED = "tool_returned"
    OUTPUT_PRODUCED = "output_produced"
    # Approval gates are events on the bus, not in-process calls.
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    # Terminal states.
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    BUDGET_EXCEEDED = "budget_exceeded"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Event(BaseModel):
    """One message on the bus.

    ``payload`` is intentionally open (a dict) so the schema doesn't have to grow
    a new field for every agent. The five top-level fields are the contract; the
    payload is the per-event-type detail (e.g. a command's text, a reply body,
    an approval's tool name).
    """

    trace_id: str = Field(..., description="Stitches one command's whole causal chain together.")
    agent_id: str = Field(..., description="Who emitted this event (e.g. 'gateway', 'echo-1a2b3c4d').")
    event_type: EventType
    timestamp: datetime = Field(default_factory=_utcnow)
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_wire(self) -> dict[str, str]:
        """Encode for a Redis stream, whose fields must be flat string values.

        We ship the whole event as one JSON string under the ``data`` field. This
        keeps the stream entry self-describing and matches what the Phase 1 trace
        writer will persist verbatim.
        """
        return {"data": self.model_dump_json()}

    @classmethod
    def from_wire(cls, fields: dict[str, str]) -> "Event":
        """Decode a Redis stream entry produced by :meth:`to_wire`."""
        return cls.model_validate_json(fields["data"])
