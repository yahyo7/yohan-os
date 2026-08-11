"""Exercise the whole email-triage agent with a stubbed Gmail transport.

The registry and approval gate stay real; only the MCP _invoke is stubbed with
fixture emails, so we can run the full workflow (search → read → classify → draft
→ gated send) without live Gmail/OAuth. An approver grants or denies the send.

Classification uses the heuristic fallback here (no Ollama), which is
deterministic: the fixtures yield 1 needs_reply, 1 spam, 1 fyi.

    uv run python scripts/smoke_triage.py         # approve the send
    uv run python scripts/smoke_triage.py deny     # deny the send
"""

from __future__ import annotations

import asyncio
import sys

from yohan_core import Bus, Event, EventType, get_settings, publish_decision
from yohan_core.tool_layer import ToolLayer

from yohan_agents.email_triage import EmailTriageAgent

_FIXTURE_UNREAD = [
    {"id": "m1", "subject": "Can you review the doc?", "from": "alice@example.com",
     "snippet": "could you take a look and confirm?"},
    {"id": "m2", "subject": "Weekly newsletter", "from": "news@promo.com",
     "snippet": "this week in tech — click here to unsubscribe"},
    {"id": "m3", "subject": "Office closed Friday", "from": "hr@example.com",
     "snippet": "the office is closed this friday for maintenance"},
]


class StubGmail(ToolLayer):
    """Real registry/gate, fixture responses instead of a live Gmail server."""

    async def _invoke(self, server: str, tool: str, arguments: dict):
        if tool == "search_emails":
            return _FIXTURE_UNREAD
        if tool == "read_email":
            return {"id": arguments["message_id"], "body": "(full email body)"}
        if tool == "send_email":
            return {"status": "sent", "to": arguments["to"]}
        return {}


class StubTriageAgent(EmailTriageAgent):
    def _make_tools(self) -> ToolLayer:
        return StubGmail(self._bus, agent_id=self._consumer)


async def _approver(bus: Bus, *, grant: bool) -> None:
    """Grant/deny the first send_email approval that appears on the results stream."""
    async for message in bus.tail(get_settings().results_stream, start="$", block_ms=2000):
        event = message.event
        if event.event_type is EventType.APPROVAL_REQUESTED:
            detail = event.payload.get("detail", {})
            print(f"  approval requested for {detail.get('tool')} → "
                  f"to={detail.get('arguments', {}).get('to')}")
            await publish_decision(
                bus,
                request_id=event.payload["request_id"],
                trace_id=event.trace_id,
                granted=grant,
                decided_by="smoke-approver",
            )
            return


async def main(grant: bool) -> int:
    agent_bus = Bus()
    approver_bus = Bus()
    await agent_bus.connect()
    await approver_bus.connect()
    try:
        agent = StubTriageAgent(bus=agent_bus)
        command = Event(
            trace_id="trc_triage_smoke",
            agent_id="test",
            event_type=EventType.COMMAND_RECEIVED,
            payload={"text": "triage my email", "reply_to": {"chat_id": 1, "message_id": 1}},
        )
        approver = asyncio.create_task(_approver(approver_bus, grant=grant))
        await asyncio.sleep(0.2)
        output = await agent.handle(command)
        await approver
        print(f"summary: {output['reply']}")
        expect = "Sent 1 reply" if grant else "declined"
        ok = expect in output["reply"]
        print("triage OK" if ok else "TRIAGE UNEXPECTED")
        return 0 if ok else 1
    finally:
        await agent_bus.aclose()
        await approver_bus.aclose()


if __name__ == "__main__":
    grant = not (len(sys.argv) > 1 and sys.argv[1] == "deny")
    raise SystemExit(asyncio.run(main(grant)))
