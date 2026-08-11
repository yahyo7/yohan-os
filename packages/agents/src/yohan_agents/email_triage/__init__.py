"""Email-triage agent — the first real agent.

An explicit workflow (not an agentic loop): its path is fixed —
search unread → read → classify → draft → send. That's faithful to the brief's
own guidance: workflows by default, agentic loops only when the path can't be
predicted. Classification goes through LiteLLM with a deterministic heuristic
fallback so the pipeline still runs with no model available; sending goes through
the tool layer, where ``gmail.send_email`` is gated and cannot fire without an
approval event.
"""

from yohan_agents.email_triage.agent import EmailTriageAgent

__all__ = ["EmailTriageAgent"]
