"""Bus client — a thin, opinionated wrapper over Redis Streams.

Design choices, all straight from the brief:

* **Streams, not pub/sub.** Streams are durable and replayable; a consumer that
  was offline still sees messages when it comes back. Pub/sub would drop them.
* **One consumer group per agent type.** All ``echo`` workers share ``grp:echo``
  and Redis load-balances entries across them — so scaling an agent type is just
  starting another process. (v1 runs one process per type, but the mechanism is
  already correct.)
* **At-least-once delivery.** We read, do the work, then ``XACK``. A crash before
  ack leaves the entry pending for redelivery rather than losing it.

Nothing here knows about Telegram, agents, or the gateway — it moves ``Event``
objects, nothing more.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator

import redis.asyncio as redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError as RedisResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError

from yohan_core.events import Event
from yohan_core.settings import CoreSettings, get_settings


@dataclass(slots=True)
class BusMessage:
    """An event read from a stream, plus the handle needed to acknowledge it.

    The caller processes ``event`` and then calls :meth:`Bus.ack` with this
    message so the entry leaves the consumer group's pending list.
    """

    stream: str
    entry_id: str
    event: Event


class Bus:
    """Async publish/consume over Redis Streams.

    Construct one per process. Call :meth:`connect` in your app's startup and
    :meth:`aclose` on shutdown (the gateway does this in its FastAPI lifespan).
    """

    def __init__(self, settings: CoreSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._redis: redis.Redis | None = None

    # --- lifecycle -------------------------------------------------------

    async def connect(self) -> None:
        if self._redis is None:
            # decode_responses=True so stream fields come back as str, not bytes.
            self._redis = redis.from_url(
                self._settings.redis_url, decode_responses=True
            )
            await self._redis.ping()

    async def aclose(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    @property
    def _client(self) -> redis.Redis:
        if self._redis is None:
            raise RuntimeError("Bus.connect() must be awaited before use.")
        return self._redis

    # --- publishing ------------------------------------------------------

    async def publish(self, stream: str, event: Event) -> str:
        """XADD an event onto a stream. Returns the Redis entry id."""
        return await self._client.xadd(stream, event.to_wire())

    async def publish_result(self, event: Event) -> str:
        """Convenience: publish onto the shared results stream.

        Agents publish their outputs/lifecycle events here; the gateway (and,
        from Phase 1, the trace writer) consume from it.
        """
        return await self.publish(self._settings.results_stream, event)

    # --- consuming -------------------------------------------------------

    async def ensure_group(self, stream: str, group: str) -> None:
        """Create the consumer group if it doesn't exist yet.

        ``mkstream=True`` lets us create the group before the stream has any
        entries. ``BUSYGROUP`` just means it already exists — harmless.
        """
        try:
            await self._client.xgroup_create(
                stream, group, id="0", mkstream=True
            )
        except RedisResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def consume(
        self,
        stream: str,
        group: str,
        consumer: str,
        *,
        block_ms: int = 5000,
        count: int = 10,
    ) -> AsyncIterator[BusMessage]:
        """Yield new events for this consumer group, forever.

        Reads with ``>`` (only entries never delivered to this group), blocking up
        to ``block_ms`` for new ones. The caller must :meth:`ack` each message
        after handling it; unacked entries stay pending for redelivery.
        """
        await self.ensure_group(stream, group)
        while True:
            try:
                response = await self._client.xreadgroup(
                    groupname=group,
                    consumername=consumer,
                    streams={stream: ">"},
                    count=count,
                    block=block_ms,
                )
            except RedisTimeoutError:
                # A blocking read that returns nothing new can surface as a socket
                # read timeout rather than an empty reply (redis-py behaviour is
                # nondeterministic here). For a long-lived consumer this is the
                # normal idle case, NOT a failure — just loop and read again.
                continue
            except RedisConnectionError:
                # Redis restarted or a connection dropped. Back off briefly and
                # retry; the group already exists so the next read resumes cleanly.
                await asyncio.sleep(1.0)
                continue
            if not response:
                continue  # block timed out with nothing new; loop again.
            for _stream_name, entries in response:
                for entry_id, fields in entries:
                    yield BusMessage(
                        stream=stream,
                        entry_id=entry_id,
                        event=Event.from_wire(fields),
                    )

    async def ack(self, message: BusMessage, group: str) -> None:
        """Acknowledge a handled message, removing it from the pending list."""
        await self._client.xack(message.stream, group, message.entry_id)

    # --- broadcast tailing (no consumer group) --------------------------

    async def tail(
        self, stream: str, *, start: str = "$", block_ms: int = 5000
    ) -> AsyncIterator[BusMessage]:
        """Yield entries from ``start`` onward with plain XREAD (no group).

        Unlike :meth:`consume`, this is broadcast: every caller keeps its own
        cursor and sees *every* entry — nothing is load-balanced away. That's what
        approval waiters need, since each parked agent must see every decision and
        filter for the one addressed to it. ``start="$"`` means "only entries added
        after this call", so a waiter won't match stale decisions.
        """
        last = start
        while True:
            try:
                response = await self._client.xread(
                    streams={stream: last}, block=block_ms
                )
            except RedisTimeoutError:
                continue
            except RedisConnectionError:
                await asyncio.sleep(1.0)
                continue
            if not response:
                continue
            for _stream_name, entries in response:
                for entry_id, fields in entries:
                    last = entry_id
                    yield BusMessage(
                        stream=stream,
                        entry_id=entry_id,
                        event=Event.from_wire(fields),
                    )
