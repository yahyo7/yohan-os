"""The email-triage workflow.

    search unread → read each → classify → (needs_reply) draft → send [gated]

``gmail.send_email`` is gated in the registry, so the ``tools.call`` for a send
parks on an approval event; the drafted reply is visible in the request, and only
an ``approval_granted`` lets it through. A denial raises ``ApprovalDenied`` and
the reply is simply skipped.

Run as a process:  ``python -m yohan_agents.email_triage.agent``
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from yohan_core import Event, ToolLayer, configure_logging
from yohan_core.tool_layer import ApprovalDenied

from yohan_agents.base import BaseAgent
from yohan_agents.email_triage.classify import classify, draft_reply

logger = logging.getLogger(__name__)


class EmailTriageAgent(BaseAgent):
    agent_type = "email_triage"

    def _make_tools(self) -> ToolLayer:
        """Construct the tool layer for a run. Overridden in tests to stub the
        transport (the registry/gate stay real)."""
        return ToolLayer(self._bus, agent_id=self._consumer)

    async def handle(self, command: Event) -> dict:
        trace_id = command.trace_id
        reply_to = command.payload.get("reply_to", {})
        counts = {"needs_reply": 0, "fyi": 0, "spam": 0, "sent": 0, "denied": 0}

        async with self._make_tools() as tools:
            search = await tools.call(
                "gmail",
                "search_emails",
                {"query": "is:unread", "max_results": 10},
                trace_id=trace_id,
            )
            emails = _parse_search(search)
            logger.info("triaging inbox", extra={"unread": len(emails)})

            for email in emails:
                full = await tools.call(
                    "gmail", "read_email", {"message_id": email["id"]}, trace_id=trace_id
                )
                body = _parse_body(full)
                category = await classify(
                    email["subject"], email["from"], email.get("snippet") or body[:200]
                )
                counts[category] += 1
                if category != "needs_reply":
                    continue

                draft = await draft_reply(email["subject"], email["from"], body)
                try:
                    # send_email is gated → this parks until approved/denied.
                    await tools.call(
                        "gmail",
                        "send_email",
                        {
                            "to": email["from"],
                            "subject": f"Re: {email['subject']}",
                            "body": draft,
                        },
                        trace_id=trace_id,
                        reply_to=reply_to,
                    )
                    counts["sent"] += 1
                except ApprovalDenied:
                    counts["denied"] += 1

        return {"reply": _format_summary(counts), "reply_to": reply_to}


# --- summary + Gmail-response parsing --------------------------------------


def _format_summary(c: dict) -> str:
    line = (
        f"Triaged inbox: {c['needs_reply']} need reply, {c['fyi']} FYI, "
        f"{c['spam']} spam."
    )
    if c["sent"]:
        line += f" Sent {c['sent']} repl{'y' if c['sent'] == 1 else 'ies'}."
    if c["denied"]:
        line += f" {c['denied']} declined."
    return line


def _extract(obj: Any) -> Any:
    """Normalize an MCP tool result to plain Python.

    A stubbed transport returns Python objects directly; the real ``mcp`` SDK
    returns a ``CallToolResult`` whose ``.content`` is a list of text parts, which
    we JSON-decode. The exact Gmail MCP output shape may need adjusting once live
    OAuth is wired — parsing is centralized here for that reason.
    """
    content = getattr(obj, "content", None)
    if content is None:
        return obj
    for part in content:
        text = getattr(part, "text", None)
        if text is not None:
            try:
                return json.loads(text)
            except (ValueError, TypeError):
                return text
    return content


def _parse_search(result: Any) -> list[dict]:
    data = _extract(result)
    if isinstance(data, dict):
        data = data.get("messages") or data.get("emails") or []
    emails = []
    for m in data or []:
        emails.append(
            {
                "id": m.get("id") or m.get("message_id") or m.get("threadId"),
                "subject": m.get("subject", "(no subject)"),
                "from": m.get("from") or m.get("sender", ""),
                "snippet": m.get("snippet", ""),
            }
        )
    return [e for e in emails if e["id"]]


def _parse_body(result: Any) -> str:
    data = _extract(result)
    if isinstance(data, dict):
        return data.get("body") or data.get("snippet") or ""
    return str(data)


def main() -> None:
    configure_logging("agent:email_triage")
    asyncio.run(EmailTriageAgent().run())


if __name__ == "__main__":
    main()
