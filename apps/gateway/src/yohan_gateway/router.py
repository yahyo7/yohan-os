"""Command → agent routing.

The brief puts the routing decision in the gateway, not in agents. In later
phases this becomes a real classifier (llama3.2:3b via LiteLLM) picking among
email-triage / briefing / devops / etc. For Phase 0 there is exactly one agent,
so the "router" is a constant — but it lives behind this seam so the call site
never changes when the classifier lands.
"""

from __future__ import annotations

# Phase 3 replaces this keyword table with the llama3.2:3b classifier.
DEFAULT_AGENT = "echo"

# Cheap keyword routing until the classifier lands.
_KEYWORDS: dict[str, tuple[str, ...]] = {
    "email_triage": ("email", "inbox", "triage", "unread"),
}


def route(text: str) -> str:
    """Return the agent_type that should handle this command's text."""
    lowered = text.lower()
    for agent_type, keywords in _KEYWORDS.items():
        if any(k in lowered for k in keywords):
            return agent_type
    return DEFAULT_AGENT
