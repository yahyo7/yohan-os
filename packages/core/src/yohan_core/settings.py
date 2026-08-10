"""Shared connection settings.

Only infra-level config lives here (Redis, Postgres, stream names) — the things
both the gateway and every agent need. App-specific config (Telegram token, the
router table) lives with the app that owns it, not in the shared core.

Values come from the environment; see ``infra/.env.example``. In dev we load
``infra/.env`` via docker-compose / the run scripts, so nothing is hardcoded.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class CoreSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="YOHAN_", extra="ignore")

    # --- Redis (the bus) ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Postgres (source of truth from Phase 1; unused by Phase 0 code) ---
    postgres_dsn: str = "postgresql://yohan:yohan@localhost:5432/yohan"

    # --- Stream naming ---
    # One Redis stream per agent type. The gateway XADDs the command onto the
    # stream for the chosen agent; that agent's consumer group reads it.
    stream_prefix: str = "yohan:stream"
    # Where agents publish results/events back for the gateway (and, later, the
    # trace writer) to consume.
    results_stream: str = "yohan:stream:results"

    def agent_stream(self, agent_type: str) -> str:
        """Stream name that a given agent type consumes commands from."""
        return f"{self.stream_prefix}:{agent_type}"


@lru_cache
def get_settings() -> CoreSettings:
    """Process-wide singleton. Cached so every module sees the same config."""
    return CoreSettings()
