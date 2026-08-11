"""LiteLLM model layer — the ONLY place a model call may happen.

The brief's rule: every model call goes through LiteLLM; no direct ``ollama.chat``
or ``anthropic.messages.create`` anywhere else. Agents ask for a *role*
(classifier / worker / reasoner) and this maps it to a configured model, so
swapping models — Ollama today, another provider tomorrow — is config, not code.

``litellm`` is imported lazily inside :func:`complete`: it's a heavy import, and
keeping it out of module load time means ``yohan_core`` stays cheap to import for
everything that doesn't call a model.
"""

from __future__ import annotations

import logging
from typing import Literal

from yohan_core.settings import get_settings

logger = logging.getLogger(__name__)

Role = Literal["classifier", "worker", "reasoner"]


def model_for(role: Role) -> str:
    """Resolve a role to the configured model id."""
    s = get_settings()
    return {
        "classifier": s.llm_classifier_model,
        "worker": s.llm_worker_model,
        "reasoner": s.llm_reasoner_model,
    }[role]


async def complete(
    messages: list[dict],
    *,
    role: Role = "worker",
    temperature: float = 0.0,
    max_tokens: int = 1024,
    timeout: float = 60.0,
    num_retries: int = 0,
    **kwargs,
) -> str:
    """Run a chat completion for the given role; return the message text.

    ``messages`` is the OpenAI-style list of ``{"role", "content"}`` dicts that
    LiteLLM normalizes across providers. For Ollama models we pass the configured
    ``api_base``; for Anthropic, LiteLLM reads ``ANTHROPIC_API_KEY`` from the env.

    ``num_retries`` defaults to 0: agents own their own retry/budget semantics,
    and failing fast lets a caller's fallback (e.g. the triage heuristic) kick in
    promptly when a local model isn't running.
    """
    import litellm

    model = model_for(role)
    call_kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "num_retries": num_retries,
        **kwargs,
    }
    if model.startswith("ollama/"):
        call_kwargs["api_base"] = get_settings().ollama_api_base

    response = await litellm.acompletion(**call_kwargs)
    return response["choices"][0]["message"]["content"] or ""
