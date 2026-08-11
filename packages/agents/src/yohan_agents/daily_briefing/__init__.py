"""Daily-briefing agent — gather several sources in parallel, compose a briefing.

Demonstrates intra-agent parallelism: the sections (email / GitHub / calendar) are
independent, so they're built concurrently with asyncio.gather and each degrades
gracefully when its source isn't connected. Scheduled by the cron-on-bus
scheduler (07:00 KST) or triggered by a command.
"""

from yohan_agents.daily_briefing.agent import DailyBriefingAgent

__all__ = ["DailyBriefingAgent"]
