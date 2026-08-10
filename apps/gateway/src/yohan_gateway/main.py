"""FastAPI gateway.

Wiring, at a glance::

    Telegram --webhook--> /telegram/webhook
                              |
                              |  command_received
                              v
                        bus: stream:<agent>          (published here)
                              |
                       (echo agent process)
                              |  output_produced
                              v
                        bus: results stream
                              |
                    results relay (this process)  --sendMessage--> Telegram

The gateway is the only process that talks to Telegram. Agents stay
channel-agnostic; they just carry the reply address through the payload and the
relay here turns ``output_produced`` back into a Telegram message.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request

from yohan_core import (
    Bus,
    Event,
    EventType,
    bind_trace_id,
    configure_logging,
    get_settings,
    new_trace_id,
)

from yohan_gateway.config import get_gateway_settings
from yohan_gateway.router import route
from yohan_gateway.telegram import parse_update, send_message

logger = logging.getLogger(__name__)

# Consumer group for the gateway's read side of the results stream.
_RESULTS_GROUP = "grp:gateway"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Own the bus connection and the results-relay task for the app's lifetime."""
    configure_logging("gateway")
    settings = get_settings()
    bus = Bus(settings)
    await bus.connect()
    app.state.bus = bus
    app.state.settings = settings

    relay = asyncio.create_task(_results_relay(bus), name="results-relay")
    logger.info("gateway up; results relay started")
    try:
        yield
    finally:
        relay.cancel()
        try:
            await relay
        except asyncio.CancelledError:
            pass
        await bus.aclose()
        logger.info("gateway down")


async def _results_relay(bus: Bus) -> None:
    """Consume the results stream and deliver replies back to Telegram.

    Runs for the life of the process. Only ``output_produced`` events carry a
    user-facing reply; every other lifecycle event (task_started, task_completed,
    …) is acked and ignored here — those are for the dashboard/trace writer in
    later phases.
    """
    settings = get_settings()
    gw = get_gateway_settings()
    async for message in bus.consume(
        settings.results_stream, _RESULTS_GROUP, "gateway-relay"
    ):
        event = message.event
        with bind_trace_id(event.trace_id):
            try:
                if event.event_type is EventType.OUTPUT_PRODUCED:
                    reply_to = event.payload.get("reply_to", {})
                    chat_id = reply_to.get("chat_id")
                    if chat_id is not None:
                        await send_message(
                            gw.telegram_api_base,
                            chat_id,
                            event.payload.get("reply", ""),
                            reply_to_message_id=reply_to.get("message_id"),
                        )
                        logger.info("relayed reply to chat %s", chat_id)
            finally:
                await bus.ack(message, _RESULTS_GROUP)


app = FastAPI(title="Yohan Gateway", version="0.0.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    """Liveness + bus reachability."""
    bus: Bus = app.state.bus
    await bus.connect()  # no-op if already connected; raises if Redis is down.
    return {"status": "ok"}


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    """Receive a Telegram update, turn it into a command event, publish it."""
    gw = get_gateway_settings()

    # Only Telegram (echoing the secret we set on the webhook) may drive this.
    if gw.telegram_webhook_secret and (
        x_telegram_bot_api_secret_token != gw.telegram_webhook_secret
    ):
        raise HTTPException(status_code=403, detail="bad webhook secret")

    update = await request.json()
    inbound = parse_update(update)
    if inbound is None:
        return {"ok": True}  # nothing we handle; ack so Telegram stops retrying.

    # Single-user guardrail: drop anyone not on the allowlist.
    allowed = gw.allowed_chat_ids
    if allowed and inbound.chat_id not in allowed:
        logger.warning("dropping command from non-allowlisted chat %s", inbound.chat_id)
        return {"ok": True}

    bus: Bus = app.state.bus
    settings = app.state.settings

    trace_id = new_trace_id()
    agent_type = route(inbound.text)
    command = Event(
        trace_id=trace_id,
        agent_id="gateway",
        event_type=EventType.COMMAND_RECEIVED,
        payload={
            "text": inbound.text,
            "channel": "telegram",
            # The reply address travels with the command so the agent can carry
            # it through to output_produced without knowing what Telegram is.
            "reply_to": {
                "chat_id": inbound.chat_id,
                "message_id": inbound.message_id,
            },
        },
    )
    with bind_trace_id(trace_id):
        await bus.publish(settings.agent_stream(agent_type), command)
        # Mirror the entry event onto the results stream so the (Phase 1) trace
        # writer records the whole lifecycle, not just what agents emit. The relay
        # ignores non-output events, so this costs the reply path nothing.
        await bus.publish_result(command)
        logger.info("routed to %s", agent_type, extra={"agent_type": agent_type})
    return {"ok": True, "trace_id": trace_id}
