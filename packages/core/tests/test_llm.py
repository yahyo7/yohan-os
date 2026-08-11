"""LLM wrapper — role→model resolution and provider routing, no live model."""

from __future__ import annotations

import sys
import types

import pytest

from yohan_core import llm


def test_model_for_maps_roles():
    assert llm.model_for("classifier").startswith("ollama/")
    assert llm.model_for("worker").startswith("ollama/")
    assert "claude" in llm.model_for("reasoner")


@pytest.mark.asyncio
async def test_complete_routes_ollama_api_base(monkeypatch):
    """Ollama models must get api_base; the wrapper returns the message text."""
    captured: dict = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return {"choices": [{"message": {"content": "needs_reply"}}]}

    fake_litellm = types.ModuleType("litellm")
    fake_litellm.acompletion = fake_acompletion
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    out = await llm.complete(
        [{"role": "user", "content": "classify this"}], role="classifier"
    )
    assert out == "needs_reply"
    assert captured["model"].startswith("ollama/")
    assert captured["api_base"]  # ollama routing supplied a base url
    assert captured["temperature"] == 0.0
