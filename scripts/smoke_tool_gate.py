"""Prove the tool layer enforces requires_approval at the boundary.

Uses a ToolLayer subclass that stubs the real MCP call, so we exercise the
enforcement path (approval gate → execute-or-block) without a live server.

Scenarios (against the real infra/mcp_registry.yaml):
  * gmail.search_emails — not gated — runs with no approver.
  * gmail.send_email     — gated — an approver watches the results stream for the
                           request and grants or denies it.

    uv run python scripts/smoke_tool_gate.py          # grant the send
    uv run python scripts/smoke_tool_gate.py deny      # deny the send
"""

from __future__ import annotations

import asyncio
import sys

from yohan_core import Bus, EventType, get_settings, publish_decision
from yohan_core.tool_layer import ApprovalDenied, ToolLayer


class StubToolLayer(ToolLayer):
    """Records whether the underlying MCP call actually fired."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.invoked: list[str] = []

    async def _invoke(self, server: str, tool: str, arguments: dict):
        self.invoked.append(f"{server}.{tool}")
        return {"ok": True, "echo": arguments}


async def _approver(bus: Bus, *, grant: bool) -> str | None:
    """Watch the results stream for an approval_requested, then decide it."""
    results = get_settings().results_stream
    async for message in bus.tail(results, start="$", block_ms=2000):
        event = message.event
        if event.event_type is EventType.APPROVAL_REQUESTED:
            rid = event.payload["request_id"]
            await publish_decision(
                bus,
                request_id=rid,
                trace_id=event.trace_id,
                granted=grant,
                decided_by="smoke-approver",
            )
            return rid
    return None


async def main(grant: bool) -> int:
    agent_bus = Bus()
    approver_bus = Bus()
    await agent_bus.connect()
    await approver_bus.connect()
    try:
        async with StubToolLayer(agent_bus, agent_id="triage-smoke") as tools:
            # 1) non-gated tool runs immediately, no approver involved.
            await tools.call("gmail", "search_emails", {"query": "is:unread"}, trace_id="trc_gate")
            assert tools.invoked == ["gmail.search_emails"], tools.invoked
            print("non-gated search_emails ran without approval ✓")

            # 2) gated tool: start the approver, then attempt the send.
            approver = asyncio.create_task(_approver(approver_bus, grant=grant))
            await asyncio.sleep(0.2)  # ensure the approver is tailing
            try:
                await tools.call(
                    "gmail", "send_email",
                    {"to": "a@b.c", "subject": "hi", "body": "…"},
                    trace_id="trc_gate",
                )
                sent = "gmail.send_email" in tools.invoked
                print(f"granted → send executed: {sent}")
                ok = grant and sent
            except ApprovalDenied as exc:
                sent = "gmail.send_email" in tools.invoked
                print(f"denied → ApprovalDenied raised, send executed: {sent} ({exc})")
                ok = (not grant) and (not sent)
            await approver
        print("gate enforced correctly ✓" if ok else "GATE FAILED")
        return 0 if ok else 1
    finally:
        await agent_bus.aclose()
        await approver_bus.aclose()


if __name__ == "__main__":
    grant = not (len(sys.argv) > 1 and sys.argv[1] == "deny")
    raise SystemExit(asyncio.run(main(grant)))
