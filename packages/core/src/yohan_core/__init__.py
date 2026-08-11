"""yohan_core — the contract shared by every process on the bus.

Nothing in this package imports the gateway or any agent. It is the base of the
dependency graph: events define the wire format, bus wraps Redis Streams, and
settings/ids are the small shared primitives everyone needs.
"""

from yohan_core.approvals import (
    Decision,
    new_request_id,
    publish_decision,
    request_and_wait,
    request_approval,
    wait_for_decision,
)
from yohan_core.bus import Bus, BusMessage
from yohan_core.db import Database
from yohan_core.dispatch import Task, dispatch, new_task_id
from yohan_core.events import Event, EventType
from yohan_core.ids import new_agent_id, new_trace_id
from yohan_core.llm import complete, model_for
from yohan_core.logging import bind_trace_id, configure_logging, get_trace_id
from yohan_core.mcp_registry import Registry, ServerSpec, ToolSpec, UnknownTool
from yohan_core.queries import (
    coerce_json_fields,
    pending_approvals,
    recent_traces,
    trace_events,
)
from yohan_core.settings import CoreSettings, get_settings
from yohan_core.skills import Skill, available_skills, load_skill
from yohan_core.tool_layer import ApprovalDenied, ToolLayer
from yohan_core.traces import apply_schema, insert_event

__all__ = [
    "Bus",
    "BusMessage",
    "Database",
    "Event",
    "EventType",
    "CoreSettings",
    "get_settings",
    "new_agent_id",
    "new_trace_id",
    "bind_trace_id",
    "configure_logging",
    "get_trace_id",
    "apply_schema",
    "insert_event",
    "Decision",
    "new_request_id",
    "publish_decision",
    "request_and_wait",
    "request_approval",
    "wait_for_decision",
    "Registry",
    "ServerSpec",
    "ToolSpec",
    "UnknownTool",
    "ToolLayer",
    "ApprovalDenied",
    "complete",
    "model_for",
    "Task",
    "dispatch",
    "new_task_id",
    "Skill",
    "load_skill",
    "available_skills",
    "recent_traces",
    "trace_events",
    "pending_approvals",
    "coerce_json_fields",
]
