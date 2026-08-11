"""BaseAgent — the consume/handle/publish loop every worker shares.

The brief's non-negotiables that live here:

* **Agents spawn on demand.** An agent is just a process running this loop; there
  are no long-lived pools in v1.
* **Every run has a budget.** Token / time / tool-call caps, hard stops. Phase 0
  wires the *shape* (the :class:`Budget` and a per-task check) but the echo agent
  is trivial enough that only the wall-clock cap can actually trip. Real
  enforcement (token accounting via LiteLLM, tool-call counting via the MCP
  client) arrives with the first real agent.
* **The bus is the only interface.** A subclass implements :meth:`handle`, which
  receives the inbound command event and returns the payload for its output. It
  never imports another agent or the gateway.
"""

from __future__ import annotations

import abc
import asyncio
import logging
import time
from dataclasses import dataclass

from yohan_core import (
    Bus,
    Event,
    EventType,
    bind_trace_id,
    get_settings,
    new_agent_id,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Budget:
    """Hard caps for a single agent run. Defaults per the brief."""

    max_tokens: int = 50_000
    max_seconds: float = 300.0  # 5 minutes
    max_tool_calls: int = 30


class BaseAgent(abc.ABC):
    """Base class for a bus worker.

    Subclasses set :attr:`agent_type` and implement :meth:`handle`. Everything
    else — group creation, the read loop, emitting lifecycle events, acking,
    and the budget clock — is handled here.
    """

    #: Stream/consumer-group key for this agent type, e.g. ``"echo"``.
    agent_type: str = ""
    #: Override per-agent if the defaults don't fit.
    budget: Budget = Budget()

    def __init__(self, bus: Bus | None = None) -> None:
        if not self.agent_type:
            raise ValueError(f"{type(self).__name__} must set `agent_type`.")
        self._settings = get_settings()
        self._bus = bus or Bus(self._settings)
        self._group = f"grp:{self.agent_type}"
        # One stable consumer name per process instance.
        self._consumer = new_agent_id(self.agent_type)

    # --- the part subclasses implement ----------------------------------

    @abc.abstractmethod
    async def handle(self, command: Event) -> dict:
        """Do the work for one command; return the ``output_produced`` payload.

        ``command`` is a ``command_received`` event routed to this agent. The
        returned dict becomes the payload of the ``output_produced`` event that
        the base loop publishes back onto the results stream.
        """

    # --- the loop, provided ---------------------------------------------

    async def run(self) -> None:
        """Connect, then consume this agent type's stream until cancelled."""
        await self._bus.connect()
        stream = self._settings.agent_stream(self.agent_type)
        logger.info(
            "agent %s (%s) consuming %s", self.agent_type, self._consumer, stream
        )
        try:
            async for message in self._bus.consume(
                stream, self._group, self._consumer
            ):
                await self._process(message.event)
                await self._bus.ack(message, self._group)
        finally:
            await self._bus.aclose()

    async def _process(self, command: Event) -> None:
        """Run one command under the budget clock, emitting lifecycle events."""
        trace_id = command.trace_id
        agent_id = self._consumer
        # A supervisor-dispatched command carries a task_id; echo it through this
        # agent's lifecycle events so the dispatcher can correlate results.
        task_id = command.payload.get("task_id")

        def tagged(payload: dict) -> dict:
            return {**payload, "task_id": task_id} if task_id else payload

        # Bind the trace_id for the whole handler: every log line from handle()
        # and every emitted event below inherits it automatically.
        with bind_trace_id(trace_id):
            await self._emit(trace_id, agent_id, EventType.TASK_STARTED, tagged({}))
            logger.info("task started", extra={"agent_type": self.agent_type})

            started = time.monotonic()
            try:
                output = await asyncio.wait_for(
                    self.handle(command), timeout=self.budget.max_seconds
                )
            except asyncio.TimeoutError:
                # Wall-clock cap is a hard stop — a budget breach, not a crash.
                logger.warning(
                    "budget exceeded: max_seconds=%s", self.budget.max_seconds
                )
                await self._emit(
                    trace_id,
                    agent_id,
                    EventType.BUDGET_EXCEEDED,
                    tagged({"limit": "max_seconds", "value": self.budget.max_seconds}),
                )
                return
            except Exception as exc:  # noqa: BLE001 — surface any failure as an event.
                logger.exception("agent %s failed", self.agent_type)
                await self._emit(
                    trace_id, agent_id, EventType.TASK_FAILED, tagged({"error": str(exc)})
                )
                return

            elapsed = time.monotonic() - started
            await self._emit(trace_id, agent_id, EventType.OUTPUT_PRODUCED, tagged(output))
            await self._emit(
                trace_id,
                agent_id,
                EventType.TASK_COMPLETED,
                tagged({"elapsed_seconds": round(elapsed, 3)}),
            )
            logger.info(
                "task completed", extra={"elapsed_seconds": round(elapsed, 3)}
            )

    async def _emit(
        self, trace_id: str, agent_id: str, event_type: EventType, payload: dict
    ) -> None:
        """Publish one lifecycle/result event back onto the results stream."""
        await self._bus.publish_result(
            Event(
                trace_id=trace_id,
                agent_id=agent_id,
                event_type=event_type,
                payload=payload,
            )
        )
