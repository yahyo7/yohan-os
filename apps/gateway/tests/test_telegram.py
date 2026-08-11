"""Telegram helpers — callback parsing and keyboard. Pure functions, no bot."""

from __future__ import annotations

from yohan_gateway.telegram import approval_keyboard, parse_callback, parse_update


def test_approval_keyboard_encodes_request_id():
    kb = approval_keyboard("apr_123")
    grant, deny = kb["inline_keyboard"][0]
    assert grant["callback_data"] == "apr:grant:apr_123"
    assert deny["callback_data"] == "apr:deny:apr_123"


def test_parse_callback_grant():
    cd = parse_callback(
        {"callback_query": {"id": "q1", "data": "apr:grant:apr_123",
                            "message": {"message_id": 5, "chat": {"id": 99}}}}
    )
    assert cd is not None
    assert cd.granted is True
    assert cd.request_id == "apr_123"
    assert cd.chat_id == 99 and cd.message_id == 5


def test_parse_callback_deny():
    cd = parse_callback(
        {"callback_query": {"id": "q", "data": "apr:deny:apr_9",
                            "message": {"message_id": 1, "chat": {"id": 1}}}}
    )
    assert cd is not None and cd.granted is False


def test_parse_callback_ignores_non_approval_and_messages():
    assert parse_callback(
        {"callback_query": {"id": "q", "data": "other:x",
                            "message": {"message_id": 1, "chat": {"id": 1}}}}
    ) is None
    assert parse_callback({"message": {"text": "hi"}}) is None


def test_parse_update_still_reads_text_messages():
    msg = parse_update(
        {"message": {"message_id": 7, "chat": {"id": 3}, "text": "hello"}}
    )
    assert msg is not None and msg.text == "hello" and msg.chat_id == 3
