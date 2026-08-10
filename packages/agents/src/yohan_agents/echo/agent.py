"""EchoAgent — the trivial Phase 0 worker.

It reads the command text out of the inbound event and returns it as the output
payload, carrying forward the reply address (chat_id) the gateway attached. That
is deliberately the *whole* job: Phase 0 exists to prove the wire, not to be
clever. The moment this round-trips text → Telegram → bus → agent → reply, the
architecture is validated and every later agent is a swap of :meth:`handle`.

Run it as a process:  ``python -m yohan_agents.echo.agent``
"""

from __future__ import annotations

import asyncio

from yohan_core import Event, configure_logging

from yohan_agents.base import BaseAgent


class EchoAgent(BaseAgent):
    agent_type = "echo"

    async def handle(self, command: Event) -> dict:
        text = command.payload.get("text", "")
        # Preserve the reply channel so the gateway knows where to send the
        # output. The agent stays channel-agnostic — it just passes the address
        # back through; the gateway owns the actual Telegram call.
        return {
            "reply": f"echo: {text}",
            "reply_to": command.payload.get("reply_to", {}),
        }


def main() -> None:
    configure_logging("agent:echo")
    asyncio.run(EchoAgent().run())


if __name__ == "__main__":
    main()
