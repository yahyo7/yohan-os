"""Structured JSON logging with trace_id propagation.

The brief's rule: ``trace_id`` propagates through every event, log, and DB row.
It's already on events and DB rows; this closes the loop for logs.

Every process calls :func:`configure_logging` once at startup. Records come out
as one JSON object per line — service, level, logger, message, timestamp, plus
``trace_id`` whenever one is bound, plus any ``extra=`` fields.

``trace_id`` rides a :class:`contextvars.ContextVar`, not a function argument, so
code deep inside an agent's handler doesn't thread it manually: the consume loop
binds it once per command (via :func:`bind_trace_id`) and every log call beneath
inherits it. ContextVars are copied per asyncio task, so concurrent requests in
the gateway never bleed each other's trace ids.

Note: ``import logging`` here is the stdlib module (absolute import), not this
file — Python 3 resolves ``yohan_core.logging`` and top-level ``logging``
distinctly.
"""

from __future__ import annotations

import contextlib
import contextvars
import datetime as _dt
import json
import logging
import sys
from typing import Iterator

_trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "yohan_trace_id", default=None
)

# Standard LogRecord attributes. Anything on a record that is NOT one of these is
# treated as a caller-supplied ``extra`` and folded into the JSON output.
_RESERVED = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName", "message", "asctime",
}


@contextlib.contextmanager
def bind_trace_id(trace_id: str) -> Iterator[None]:
    """Bind ``trace_id`` for the duration so logs underneath carry it."""
    token = _trace_id_var.set(trace_id)
    try:
        yield
    finally:
        _trace_id_var.reset(token)


def get_trace_id() -> str | None:
    """The trace_id bound in the current context, if any."""
    return _trace_id_var.get()


class JsonFormatter(logging.Formatter):
    """One compact JSON object per record, enriched with the bound trace_id."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": _dt.datetime.fromtimestamp(
                record.created, _dt.timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "service": self._service,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        trace_id = _trace_id_var.get()
        if trace_id is not None:
            payload["trace_id"] = trace_id
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Fold in any extra=... fields the caller attached to the record.
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(service: str, *, level: int | str = logging.INFO) -> None:
    """Install the JSON handler on the root logger. Idempotent per process.

    ``service`` labels which process emitted the line (e.g. ``gateway``,
    ``agent:echo``, ``trace_writer``). We replace root handlers so a host that
    pre-configured logging (uvicorn, streamlit) doesn't cause double lines for
    our own loggers.
    """
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    root.addHandler(handler)
