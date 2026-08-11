"""Supervisor — plan a command into sub-tasks and dispatch them in parallel.

The orchestrator: it turns one command into a plan (a list of tasks for other
agents), fans them out concurrently via yohan_core.dispatch, and aggregates the
results into one reply. It emits plan_created / task_assigned so the plan is
visible in the trace. Sub-tasks carry no reply_to — the supervisor owns the one
user-facing reply, so nothing is double-sent.
"""

from yohan_agents.supervisor.agent import SupervisorAgent

__all__ = ["SupervisorAgent"]
