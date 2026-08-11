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

from fastapi.middleware.cors import CORSMiddleware

from yohan_core import (
    Bus,
    Database,
    Event,
    EventType,
    bind_trace_id,
    configure_logging,
    get_settings,
    new_trace_id,
    publish_decision,
)

from yohan_gateway.dashboard_api import router as dashboard_router

from yohan_gateway.config import get_gateway_settings
from yohan_gateway.router import route
from yohan_gateway.telegram import (
    answer_callback_query,
    approval_keyboard,
    edit_message_text,
    parse_callback,
    parse_update,
    send_message,
)

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
    db = Database(settings)
    await db.connect()  # dashboard API reads the traces store
    app.state.bus = bus
    app.state.db = db
    app.state.settings = settings
    # request_id -> {trace_id, chat_id, message_id} for approval buttons in flight.
    # In-memory is fine for a single-user gateway; a restart mid-approval just
    # means the button's decision is published without the original trace_id.
    app.state.pending_approvals = {}

    relay = asyncio.create_task(
        _results_relay(bus, app.state.pending_approvals), name="results-relay"
    )
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
        await db.aclose()
        logger.info("gateway down")


async def _results_relay(bus: Bus, pending: dict) -> None:
    """Consume the results stream and drive Telegram output.

    Two event types matter here: ``output_produced`` (deliver the reply) and
    ``approval_requested`` (prompt the user with Approve/Reject buttons). Every
    other lifecycle event is acked and ignored — those are for the trace writer.
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
                elif event.event_type is EventType.APPROVAL_REQUESTED:
                    await _prompt_approval(gw, event, pending)
            finally:
                await bus.ack(message, _RESULTS_GROUP)


async def _prompt_approval(gw, event: Event, pending: dict) -> None:
    """Send an Approve/Reject prompt to Telegram for one approval request."""
    payload = event.payload
    request_id = payload.get("request_id")
    reply_to = payload.get("reply_to", {})
    chat_id = reply_to.get("chat_id")
    if request_id is None or chat_id is None:
        return
    pending[request_id] = {"trace_id": event.trace_id, "chat_id": chat_id}
    await send_message(
        gw.telegram_api_base,
        chat_id,
        _format_approval(payload),
        reply_markup=approval_keyboard(request_id),
    )
    logger.info("prompted approval %s to chat %s", request_id, chat_id)


def _format_approval(payload: dict) -> str:
    """Human-readable approval prompt from the request payload."""
    action = payload.get("action", "action")
    detail = payload.get("detail", {})
    args = detail.get("arguments", {})
    if action == "gmail.send_email":
        body = str(args.get("body", ""))
        preview = body if len(body) <= 300 else body[:300] + "…"
        return (
            f"🔐 Approve sending this email?\n"
            f"To: {args.get('to', '')}\n"
            f"Subject: {args.get('subject', '')}\n\n{preview}"
        )
    return f"🔐 Approve {action}?\n{args}"


async def _handle_callback(gw, callback) -> None:
    """Turn an Approve/Reject tap into an approval decision on the bus."""
    bus: Bus = app.state.bus
    pending: dict = app.state.pending_approvals
    context = pending.pop(callback.request_id, {})
    trace_id = context.get("trace_id", "")

    with bind_trace_id(trace_id or "unknown"):
        await publish_decision(
            bus,
            request_id=callback.request_id,
            trace_id=trace_id,
            granted=callback.granted,
            decided_by="telegram",
        )
        verdict = "approved ✅" if callback.granted else "rejected ❌"
        await answer_callback_query(gw.telegram_api_base, callback.callback_query_id, verdict)
        # Replace the prompt so the buttons can't be tapped twice.
        await edit_message_text(
            gw.telegram_api_base, callback.chat_id, callback.message_id,
            f"Decision recorded: {verdict}",
        )
        logger.info("approval %s %s", callback.request_id, verdict)


app = FastAPI(title="Yohan Gateway", version="0.0.0", lifespan=lifespan)

# The Next.js dashboard runs on :3000 and calls this API cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(dashboard_router)


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

    # An inline-button tap (approve/reject) rather than a message?
    callback = parse_callback(update)
    if callback is not None:
        await _handle_callback(gw, callback)
        return {"ok": True}

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
