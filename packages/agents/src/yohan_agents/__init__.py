"""yohan_agents — worker agents that live on the bus.

An agent is a process that consumes command events from its own stream, does its
job, and publishes result events back. Phase 0 ships exactly one, ``echo``, to
prove the cross-process loop end to end.
"""

from yohan_agents.base import BaseAgent, Budget
from yohan_agents.echo import EchoAgent
from yohan_agents.email_triage import EmailTriageAgent

__all__ = ["BaseAgent", "Budget", "EchoAgent", "EmailTriageAgent"]
