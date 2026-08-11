"""Email-triage pure logic — heuristics, parsing, summary. No services needed."""

from __future__ import annotations

from yohan_agents.email_triage.agent import (
    _format_summary,
    _parse_body,
    _parse_search,
)
from yohan_agents.email_triage.classify import heuristic_category


def test_heuristic_spam():
    assert heuristic_category("You won!", "x@y", "click here to unsubscribe") == "spam"


def test_heuristic_needs_reply():
    assert heuristic_category("Quick q", "x@y", "can you confirm the date?") == "needs_reply"


def test_heuristic_fyi():
    assert heuristic_category("Notes", "x@y", "the office is closed friday") == "fyi"


def test_parse_search_handles_field_variants():
    emails = _parse_search(
        [
            {"id": "m1", "subject": "s", "from": "a@b"},
            {"message_id": "m2", "sender": "c@d"},  # alternate field names
            {"subject": "no id — dropped"},
        ]
    )
    assert [e["id"] for e in emails] == ["m1", "m2"]
    assert emails[1]["from"] == "c@d"


def test_parse_search_dict_wrapper():
    emails = _parse_search({"messages": [{"id": "x", "subject": "s"}]})
    assert emails[0]["id"] == "x"


def test_parse_body():
    assert _parse_body({"body": "hello"}) == "hello"
    assert _parse_body({"snippet": "fallback"}) == "fallback"


def test_format_summary_counts_and_sent():
    s = _format_summary(
        {"needs_reply": 1, "fyi": 2, "spam": 1, "sent": 1, "denied": 0}
    )
    assert "1 need reply" in s and "2 FYI" in s and "1 spam" in s
    assert "Sent 1 reply" in s
