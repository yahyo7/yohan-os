"""Registry loading + policy lookup — no external services needed."""

from __future__ import annotations

import textwrap

import pytest

from yohan_core.mcp_registry import Registry, UnknownTool


def _registry(tmp_path) -> Registry:
    p = tmp_path / "reg.yaml"
    p.write_text(
        textwrap.dedent(
            """
            servers:
              gmail:
                command: npx
                args: ["-y", "server-gmail"]
                tools:
                  search_emails:
                    requires_approval: false
                  send_email:
                    requires_approval: true
            """
        )
    )
    return Registry.load(p)


def test_reads_command_and_args(tmp_path):
    reg = _registry(tmp_path)
    gmail = reg.server("gmail")
    assert gmail.command == "npx"
    assert gmail.args == ["-y", "server-gmail"]


def test_requires_approval_policy(tmp_path):
    reg = _registry(tmp_path)
    assert reg.requires_approval("gmail", "send_email") is True
    assert reg.requires_approval("gmail", "search_emails") is False


def test_unknown_tool_or_server_raises(tmp_path):
    reg = _registry(tmp_path)
    with pytest.raises(UnknownTool):
        reg.tool("gmail", "nope")
    with pytest.raises(UnknownTool):
        reg.server("slack")


def test_repo_registry_marks_send_as_gated():
    """The real infra/mcp_registry.yaml must gate gmail.send_email."""
    reg = Registry.load()
    assert reg.requires_approval("gmail", "send_email") is True
    assert reg.requires_approval("gmail", "search_emails") is False
