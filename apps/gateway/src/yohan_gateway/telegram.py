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
    api_base: str, chat_id: int, text: str, *, reply_to_message_id: int | None = None
) -> None:
    """Send a text reply via the Bot API's sendMessage."""
    payload: dict = {"chat_id": chat_id, "text": text}
    if reply_to_message_id is not None:
        payload["reply_parameters"] = {"message_id": reply_to_message_id}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{api_base}/sendMessage", json=payload)
        if resp.status_code != 200:
            logger.error("sendMessage failed: %s %s", resp.status_code, resp.text)
