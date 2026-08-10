"""Postgres access — a thin asyncpg pool wrapper.

The brief calls for ``asyncpg`` for raw queries (and SQLAlchemy only where an ORM
earns its keep — it doesn't yet). This module owns pool lifecycle so every process
that needs Postgres gets it the same way, from the same DSN as ``CoreSettings``.

Phase 0 didn't touch Postgres at all; Phase 1's trace writer is the first user.
"""

from __future__ import annotations

import asyncpg

from yohan_core.settings import CoreSettings, get_settings


class Database:
    """Owns an asyncpg connection pool for one process."""

    def __init__(self, settings: CoreSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self._settings.postgres_dsn,
                min_size=1,
                max_size=5,
            )

    async def aclose(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database.connect() must be awaited before use.")
        return self._pool
