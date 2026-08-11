"""Run the daily-briefing agent with a stubbed Gmail transport.

Shows the email section rendering from fixture data and the parallel section
compose, without live Gmail/OAuth.

    uv run python scripts/smoke_briefing.py
"""

from __future__ import annotations

import asyncio

from yohan_core import Bus, Event, EventType
from yohan_core.tool_layer import ToolLayer

from yohan_agents.daily_briefing import DailyBriefingAgent

_FIXTURE_URGENT = [
    {"id": "m1", "subject": "Prod incident — API 5xx spike", "from": "oncall@co.com"},
    {"id": "m2", "subject": "Contract signature needed today", "from": "legal@co.com"},
]


class StubGmail(ToolLayer):
    async def _invoke(self, server: str, tool: str, arguments: dict):
        if tool == "search_emails":
            return _FIXTURE_URGENT
        return {}


class StubBriefing(DailyBriefingAgent):
    def _make_tools(self) -> ToolLayer:
        return StubGmail(self._bus, agent_id=self._consumer)


async def main() -> int:
    bus = Bus()
    await bus.connect()
    try:
        agent = StubBriefing(bus=bus)
        command = Event(
            trace_id="trc_brief_smoke",
            agent_id="test",
            event_type=EventType.COMMAND_RECEIVED,
            payload={"reply_to": {}},
        )
        output = await agent.handle(command)
        print(output["reply"])
        ok = "Prod incident" in output["reply"] and "GitHub" in output["reply"]
        print("\nbriefing composed ✓" if ok else "\nBRIEFING FAILED")
        return 0 if ok else 1
    finally:
        await bus.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
