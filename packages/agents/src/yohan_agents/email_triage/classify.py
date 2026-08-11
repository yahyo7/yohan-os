"""Classification and draft generation for email triage.

Both go through LiteLLM (``yohan_core.llm``) but fall back to deterministic logic
when no model is reachable — so the pipeline stays runnable and testable without
Ollama or an API key. The fallback is clearly a fallback, not a second code path
that quietly replaces the model.
"""

from __future__ import annotations

import logging
from typing import Literal

from yohan_core import complete

logger = logging.getLogger(__name__)

Category = Literal["needs_reply", "fyi", "spam"]
CATEGORIES: tuple[Category, ...] = ("needs_reply", "fyi", "spam")

_SPAM_HINTS = (
    "unsubscribe", "lottery", "viagra", "free money", "click here",
    "limited time", "act now", "winner",
)
_REPLY_HINTS = (
    "?", "can you", "could you", "please", "let me know", "thoughts",
    "confirm", "are you available", "get back to me",
)


def heuristic_category(subject: str, sender: str, snippet: str) -> Category:
    """Rule-based fallback classifier. Deterministic — used when the LLM is down."""
    text = f"{subject} {snippet}".lower()
    if any(h in text for h in _SPAM_HINTS):
        return "spam"
    if any(h in text for h in _REPLY_HINTS):
        return "needs_reply"
    return "fyi"


async def classify(subject: str, sender: str, snippet: str) -> Category:
    """Classify one email; fall back to heuristics if the model call fails."""
    prompt = (
        "Classify this email into exactly one label: needs_reply, fyi, or spam.\n"
        f"From: {sender}\nSubject: {subject}\nSnippet: {snippet}\n"
        "Answer with only the label."
    )
    try:
        out = (await complete(
            [{"role": "user", "content": prompt}], role="classifier", max_tokens=8
        )).strip().lower()
        for category in CATEGORIES:
            if category in out:
                return category
        # Model answered something unexpected — fall back rather than guess.
        return heuristic_category(subject, sender, snippet)
    except Exception:  # noqa: BLE001 — any model/transport failure → heuristic.
        logger.warning("classifier unavailable; using heuristic fallback")
        return heuristic_category(subject, sender, snippet)


async def draft_reply(subject: str, sender: str, body: str) -> str:
    """Draft a short reply; fall back to a safe template if the model is down."""
    prompt = (
        "Write a brief, polite reply to this email. Keep it under 120 words. "
        "Do not invent facts or commitments.\n\n"
        f"From: {sender}\nSubject: {subject}\n\n{body}"
    )
    try:
        return (await complete(
            [{"role": "user", "content": prompt}], role="worker", max_tokens=300
        )).strip()
    except Exception:  # noqa: BLE001
        logger.warning("draft model unavailable; using template fallback")
        return (
            f"Thanks for your email regarding “{subject}”. "
            "I've received it and will follow up shortly."
        )
