"""yohan_agents — worker agents that live on the bus.

An agent is a process that consumes command events from its own stream, does its
job, and publishes result events back. Phase 0 ships exactly one, ``echo``, to
prove the cross-process loop end to end.
"""

from yohan_agents.base import BaseAgent, Budget

__all__ = ["BaseAgent", "Budget"]
