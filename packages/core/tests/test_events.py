"""Contract tests — the wire format must round-trip exactly.

These need no Redis: they check that an Event survives to_wire/from_wire, which
is what both the bus and (Phase 1) the trace writer rely on.
"""

from __future__ import annotations

from yohan_core import Event, EventType


def test_event_roundtrips_through_wire():
    original = Event(
        trace_id="trc_abc",
        agent_id="echo-1234",
        event_type=EventType.OUTPUT_PRODUCED,
        payload={"reply": "echo: hi", "reply_to": {"chat_id": 42, "message_id": 7}},
    )
    restored = Event.from_wire(original.to_wire())

    assert restored.trace_id == original.trace_id
    assert restored.agent_id == original.agent_id
    assert restored.event_type is EventType.OUTPUT_PRODUCED
    assert restored.payload == original.payload
    # timestamp survives serialization (tz-aware)
    assert restored.timestamp == original.timestamp


def test_event_type_serializes_as_plain_string():
    wire = Event(
        trace_id="t", agent_id="a", event_type=EventType.COMMAND_RECEIVED
    ).to_wire()
    # The stream field is a single JSON blob; the enum must be its string value.
    assert '"command_received"' in wire["data"]
