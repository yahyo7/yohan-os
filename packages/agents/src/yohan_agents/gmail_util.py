"""Shared parsing for Gmail MCP tool results.

Used by both the email-triage and daily-briefing agents. A stubbed transport
returns plain Python; the real ``mcp`` SDK returns a ``CallToolResult`` whose
``.content`` is a list of text parts, which we JSON-decode. The exact Gmail MCP
output shape may need adjusting once live OAuth is wired — it's centralized here.
"""

from __future__ import annotations

import json
from typing import Any


def extract_result(obj: Any) -> Any:
    """Normalize an MCP tool result to plain Python."""
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


def parse_search(result: Any) -> list[dict]:
    """A Gmail search result → a list of ``{id, subject, from, snippet}``."""
    data = extract_result(result)
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


def parse_body(result: Any) -> str:
    """A Gmail read result → the message body text."""
    data = extract_result(result)
    if isinstance(data, dict):
        return data.get("body") or data.get("snippet") or ""
    return str(data)
