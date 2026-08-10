"""Gateway-specific config.

Shared infra config (Redis, streams) comes from ``yohan_core.get_settings()``.
What lives here is only what the gateway owns: the Telegram bot token, a webhook
secret, and the chat allowlist. Single-user system — the allowlist is how we keep
it that way without building auth (explicitly out of scope for v1).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="YOHAN_", extra="ignore")

    # From @BotFather.
    telegram_bot_token: str = ""
    # Telegram echoes this header on every webhook call; we reject mismatches so
    # only Telegram (via our Cloudflare Tunnel) can drive the gateway.
    telegram_webhook_secret: str = ""
    # Comma-separated Telegram chat ids allowed to command the system. Empty =
    # allow all (dev only — set this before exposing the tunnel).
    telegram_allowed_chat_ids: str = ""

    @property
    def allowed_chat_ids(self) -> set[int]:
        raw = self.telegram_allowed_chat_ids.strip()
        if not raw:
            return set()
        return {int(x) for x in raw.split(",") if x.strip()}

    @property
    def telegram_api_base(self) -> str:
        return f"https://api.telegram.org/bot{self.telegram_bot_token}"


@lru_cache
def get_gateway_settings() -> GatewaySettings:
    return GatewaySettings()
