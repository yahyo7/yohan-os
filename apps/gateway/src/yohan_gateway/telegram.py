"""Telegram Bot API glue.

Two directions:

* **Inbound** — Telegram POSTs updates to our webhook. :func:`parse_update`
  pulls the bits we care about (chat id, message id, text) out of the raw update.
* **Outbound** — :func:`send_message` calls the Bot API to deliver a reply.

Phase 0 handles text only. Voice notes (download + ``mlx-whisper`` transcription)
are Phase 6; :func:`parse_update` simply ignores non-text messages for now.

We use raw httpx rather than python-telegram-bot here because Phase 0 needs only
two API surfaces (webhook receive + sendMessage) and staying thin keeps the wire
obvious. The heavier library comes in when we add inline approval buttons.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class InboundMessage:
    """The subset of a Telegram update the gateway acts on."""

    chat_id: int
    message_id: int
    text: str


@dataclass(slots=True)
class CallbackDecision:
    """A parsed inline-button tap: an approve/reject for a request_id."""

    callback_query_id: str
    chat_id: int
    message_id: int
    request_id: str
    granted: bool


def parse_callback(update: dict) -> CallbackDecision | None:
    """Extract an approve/reject button tap, if this update is one.

    Our callback_data is ``"apr:grant:<request_id>"`` / ``"apr:deny:<request_id>"``
    (well under Telegram's 64-byte limit — request ids are short).
    """
    cq = update.get("callback_query")
    if not cq:
        return None
    data = cq.get("data", "")
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "apr":
        return None
    _, verb, request_id = parts
    message = cq.get("message", {})
    chat = message.get("chat", {})
    if chat.get("id") is None or message.get("message_id") is None:
        return None
    return CallbackDecision(
        callback_query_id=cq.get("id", ""),
        chat_id=chat["id"],
        message_id=message["message_id"],
        request_id=request_id,
        granted=(verb == "grant"),
    )


def approval_keyboard(request_id: str) -> dict:
    """Inline keyboard with Approve / Reject buttons for one request."""
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Approve", "callback_data": f"apr:grant:{request_id}"},
                {"text": "❌ Reject", "callback_data": f"apr:deny:{request_id}"},
            ]
        ]
    }


def parse_update(update: dict) -> InboundMessage | None:
    """Extract an :class:`InboundMessage` from a raw Telegram update.

    Returns ``None`` for anything we don't handle in Phase 0 (edits, non-text
    messages, updates without a message) so the webhook can 200-and-ignore.
    """
    message = update.get("message")
    if not message:
        return None
    text = message.get("text")
    if not text:
        return None
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    if chat_id is None or message_id is None:
        return None
    return InboundMessage(chat_id=chat_id, message_id=message_id, text=text)


async def send_message(
    api_base: str,
    chat_id: int,
    text: str,
    *,
    reply_to_message_id: int | None = None,
    reply_markup: dict | None = None,
) -> None:
    """Send a text reply via the Bot API's sendMessage (optionally with buttons)."""
    payload: dict = {"chat_id": chat_id, "text": text}
    if reply_to_message_id is not None:
        payload["reply_parameters"] = {"message_id": reply_to_message_id}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{api_base}/sendMessage", json=payload)
        if resp.status_code != 200:
            logger.error("sendMessage failed: %s %s", resp.status_code, resp.text)


async def answer_callback_query(api_base: str, callback_query_id: str, text: str) -> None:
    """Acknowledge a button tap so Telegram stops the loading spinner."""
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"{api_base}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text},
        )


async def edit_message_text(
    api_base: str, chat_id: int, message_id: int, text: str
) -> None:
    """Replace a message's text (and drop its buttons) after a decision."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{api_base}/editMessageText",
            json={"chat_id": chat_id, "message_id": message_id, "text": text},
        )
        if resp.status_code != 200:
            logger.error("editMessageText failed: %s %s", resp.status_code, resp.text)
