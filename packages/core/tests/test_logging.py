"""Tests for structured logging — no external services needed."""

from __future__ import annotations

import json
import logging

from yohan_core.logging import JsonFormatter, bind_trace_id, get_trace_id


def _record(msg: str = "hello") -> logging.LogRecord:
    return logging.LogRecord("test.logger", logging.INFO, __file__, 1, msg, None, None)


def test_formatter_includes_bound_trace_id():
    fmt = JsonFormatter("gateway")
    with bind_trace_id("trc_abc"):
        out = json.loads(fmt.format(_record()))
    assert out["trace_id"] == "trc_abc"
    assert out["service"] == "gateway"
    assert out["logger"] == "test.logger"
    assert out["level"] == "INFO"
    assert out["msg"] == "hello"


def test_formatter_omits_trace_id_when_unbound():
    out = json.loads(JsonFormatter("svc").format(_record()))
    assert "trace_id" not in out


def test_extra_fields_are_folded_in():
    rec = _record()
    rec.agent_type = "echo"  # what logging does for extra={"agent_type": "echo"}
    out = json.loads(JsonFormatter("svc").format(rec))
    assert out["agent_type"] == "echo"


def test_bind_trace_id_sets_and_resets():
    assert get_trace_id() is None
    with bind_trace_id("a"):
        assert get_trace_id() == "a"
        with bind_trace_id("b"):
            assert get_trace_id() == "b"
        assert get_trace_id() == "a"  # inner reset restores outer
    assert get_trace_id() is None
