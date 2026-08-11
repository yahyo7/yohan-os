"""The daily-briefing workflow.

Builds the sections concurrently, then composes one message. Each section catches
its own failures and returns a graceful placeholder, so an unconnected source
(GitHub/calendar aren't in the registry yet; Gmail needs OAuth) degrades the
briefing rather than breaking it.

Run as a process:  ``python -m yohan_agents.daily_briefing.agent``
"""

from __future__ import annotations

import asyncio
import logging

from yohan_core import Event, ToolLayer, configure_logging

from yohan_agents.base import BaseAgent
from yohan_agents.gmail_util import parse_search

logger = logging.getLogger(__name__)


class DailyBriefingAgent(BaseAgent):
    agent_type = "daily_briefing"

    def _make_tools(self) -> ToolLayer:
        """Seam for tests to stub the transport (registry stays real)."""
        return ToolLayer(self._bus, agent_id=self._consumer)

    async def handle(self, command: Event) -> dict:
        trace_id = command.trace_id
        reply_to = command.payload.get("reply_to", {})

        async with self._make_tools() as tools:
            # Sections are independent → gather them concurrently.
            email, github, calendar = await asyncio.gather(
                self._email_section(tools, trace_id),
                self._github_section(),
                self._calendar_section(),
            )

        briefing = "🌅 *Daily briefing*\n\n" + "\n\n".join([email, github, calendar])
        return {"reply": briefing, "reply_to": reply_to}

    async def _email_section(self, tools: ToolLayer, trace_id: str) -> str:
        try:
            result = await tools.call(
                "gmail",
                "search_emails",
                {"query": "is:unread is:important", "max_results": 10},
                trace_id=trace_id,
            )
            emails = parse_search(result)
            if not emails:
                return "📧 Email — inbox clear, no urgent unread."
            lines = [f"• {e['subject']} — {e['from']}" for e in emails[:5]]
            more = f"\n…and {len(emails) - 5} more" if len(emails) > 5 else ""
            return f"📧 Email — {len(emails)} urgent unread:\n" + "\n".join(lines) + more
        except Exception:  # noqa: BLE001 — a section never breaks the briefing.
            logger.warning("email section unavailable")
            return "📧 Email — (Gmail not connected)"

    async def _github_section(self) -> str:
        # Placeholder until a GitHub MCP server is in the registry (Phase 4+).
        return "🐙 GitHub — (not connected)"

    async def _calendar_section(self) -> str:
        # Placeholder until a calendar MCP server is in the registry (Phase 4+).
        return "📅 Calendar — (not connected)"


def main() -> None:
    configure_logging("agent:daily_briefing")
    asyncio.run(DailyBriefingAgent().run())


if __name__ == "__main__":
    main()
