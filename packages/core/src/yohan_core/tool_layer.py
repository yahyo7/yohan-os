"""The tool layer — every tool call goes through here.

The brief's rules this enforces:

* Every tool call goes through an MCP client (no direct API calls in agent code).
* Every side-effectful tool declares ``requires_approval``, enforced *at the tool
  layer* — a gated tool physically cannot execute until an approval event clears
  it. The check is here, not in a prompt.
* ``trace_id`` propagates: each call emits ``tool_called`` / ``tool_returned``
  onto the results stream, so the trace and dashboard see tool activity.

The gate uses the bus-native approval primitive (:mod:`yohan_core.approvals`).
The actual MCP invocation (:meth:`_invoke`) is isolated so the enforcement path
can be tested without a live server — a test subclass stubs it.
"""

from __future__ import annotations

import logging
import os
from contextlib import AsyncExitStack
from typing import Any

from yohan_core.approvals import request_and_wait
from yohan_core.bus import Bus
from yohan_core.events import Event, EventType
from yohan_core.mcp_registry import Registry

logger = logging.getLogger(__name__)


class ApprovalDenied(Exception):
    """Raised when a gated tool call is denied — the call does not execute."""


class ToolLayer:
    """MCP client + approval enforcement for one agent run.

    Use as an async context manager so server sessions are opened lazily and
    torn down together::

        async with ToolLayer(bus, agent_id="triage-1") as tools:
            await tools.call("gmail", "search_emails", {"query": "is:unread"},
                             trace_id=trace_id)
    """

    def __init__(
        self, bus: Bus, *, agent_id: str, registry: Registry | None = None
    ) -> None:
        self._bus = bus
        self._agent_id = agent_id
        self._registry = registry or Registry.load()
        self._stack = AsyncExitStack()
        self._sessions: dict[str, Any] = {}

    async def __aenter__(self) -> "ToolLayer":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._stack.aclose()
        self._sessions.clear()

    async def call(
        self,
        server: str,
        tool: str,
        arguments: dict,
        *,
        trace_id: str,
        reply_to: dict | None = None,
    ) -> Any:
        """Call a tool, enforcing its approval policy first.

        Raises :class:`ApprovalDenied` if a gated call is rejected, and
        ``TimeoutError`` if no decision arrives in time.
        """
        if self._registry.requires_approval(server, tool):
            decision = await request_and_wait(
                self._bus,
                trace_id=trace_id,
                agent_id=self._agent_id,
                action=f"{server}.{tool}",
                detail={"server": server, "tool": tool, "arguments": arguments},
                reply_to=reply_to,
            )
            if not decision.granted:
                logger.warning("tool %s.%s denied by %s", server, tool, decision.decided_by)
                raise ApprovalDenied(f"{server}.{tool} denied by {decision.decided_by}")
            logger.info("tool %s.%s approved by %s", server, tool, decision.decided_by)

        await self._emit(trace_id, EventType.TOOL_CALLED, {
            "server": server, "tool": tool, "arguments": arguments,
        })
        result = await self._invoke(server, tool, arguments)
        await self._emit(trace_id, EventType.TOOL_RETURNED, {
            "server": server, "tool": tool, "result": _summarize(result),
        })
        return result

    # --- the actual MCP call (isolated for testability) ------------------

    async def _invoke(self, server: str, tool: str, arguments: dict) -> Any:
        """Invoke the tool over stdio via the official MCP SDK.

        Sessions are cached per server for the layer's lifetime, so we don't
        respawn the server subprocess on every call.
        """
        session = await self._session(server)
        return await session.call_tool(tool, arguments)

    async def _session(self, server: str) -> Any:
        if server in self._sessions:
            return self._sessions[server]
        spec = self._registry.server(server)
        # Lazy import so core doesn't hard-depend on the SDK at import time.
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command=spec.command,
            args=spec.args,
            env={**os.environ, **spec.env} if spec.env else None,
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        session = await self._stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._sessions[server] = session
        return session

    async def _emit(self, trace_id: str, event_type: EventType, payload: dict) -> None:
        await self._bus.publish_result(
            Event(
                trace_id=trace_id,
                agent_id=self._agent_id,
                event_type=event_type,
                payload=payload,
            )
        )


def _summarize(result: Any, *, limit: int = 500) -> str:
    """Compact, JSON-safe string form of a tool result for the trace row."""
    text = getattr(result, "content", result)
    text = str(text)
    return text if len(text) <= limit else text[:limit] + "…"
