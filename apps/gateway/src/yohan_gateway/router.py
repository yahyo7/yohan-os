"""Command → agent routing.

The brief puts the routing decision in the gateway, not in agents. In later
phases this becomes a real classifier (llama3.2:3b via LiteLLM) picking among
email-triage / briefing / devops / etc. For Phase 0 there is exactly one agent,
so the "router" is a constant — but it lives behind this seam so the call site
never changes when the classifier lands.
"""

from __future__ import annotations

# Phase 0: everything goes to echo. Phase 3 replaces this body with a classifier.
DEFAULT_AGENT = "echo"


def route(text: str) -> str:
    """Return the agent_type that should handle this command's text."""
    return DEFAULT_AGENT
