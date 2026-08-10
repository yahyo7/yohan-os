"""yohan_core — the contract shared by every process on the bus.

Nothing in this package imports the gateway or any agent. It is the base of the
dependency graph: events define the wire format, bus wraps Redis Streams, and
settings/ids are the small shared primitives everyone needs.
"""

from yohan_core.bus import Bus, BusMessage
from yohan_core.events import Event, EventType
from yohan_core.ids import new_agent_id, new_trace_id
from yohan_core.settings import CoreSettings, get_settings

__all__ = [
    "Bus",
    "BusMessage",
    "Event",
    "EventType",
    "CoreSettings",
    "get_settings",
    "new_agent_id",
    "new_trace_id",
]
