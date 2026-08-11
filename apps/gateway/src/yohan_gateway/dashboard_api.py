"""Dashboard API — SSE live stream + REST over the traces store.

Served by the same FastAPI app as the Telegram webhook. The Next.js dashboard
(Phase 5) consumes these:

* GET  /api/events              — SSE; every bus event as it happens (live DAG/feed)
* GET  /api/traces              — recent commands (history)
* GET  /api/traces/{trace_id}   — one command's full event list (build its DAG)
* GET  /api/approvals           — pending approvals (action queue)
* POST /api/approvals/{id}      — approve/reject (publishes the decision)

Read endpoints go through yohan_core.queries; the decision endpoint reuses the
same bus-native publish_decision the Telegram buttons use.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from yohan_core import (
    coerce_json_fields,
    get_settings,
    pending_approvals,
    publish_decision,
    recent_traces,
    trace_events,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/traces")
async def api_traces(request: Request, limit: int = 50) -> list[dict]:
    return await recent_traces(request.app.state.db.pool, limit=limit)


@router.get("/traces/{trace_id}")
async def api_trace(request: Request, trace_id: str) -> list[dict]:
    rows = await trace_events(request.app.state.db.pool, trace_id)
    return coerce_json_fields(rows, ("payload",))


@router.get("/approvals")
async def api_approvals(request: Request) -> list[dict]:
    rows = await pending_approvals(request.app.state.db.pool)
    return coerce_json_fields(rows, ("arguments",))


class DecisionBody(BaseModel):
    granted: bool


@router.post("/approvals/{request_id}")
async def api_decide(request: Request, request_id: str, body: DecisionBody) -> dict:
    # Best-effort trace_id for the decision event (tracing only; the waiting agent
    # matches on request_id).
    pend = await pending_approvals(request.app.state.db.pool)
    trace_id = next((p["trace_id"] for p in pend if p["request_id"] == request_id), "")
    await publish_decision(
        request.app.state.bus,
        request_id=request_id,
        trace_id=trace_id,
        granted=body.granted,
        decided_by="dashboard",
    )
    return {"ok": True, "request_id": request_id, "granted": body.granted}


@router.get("/events")
async def api_events(request: Request) -> StreamingResponse:
    """Server-Sent Events: one JSON event per bus event, live from now."""
    settings = get_settings()
    bus = request.app.state.bus

    async def gen():
        # Prime the stream so the client's onopen fires immediately.
        yield ": connected\n\n"
        try:
            async for message in bus.tail(
                settings.results_stream, start="$", block_ms=15000
            ):
                yield f"data: {message.event.model_dump_json()}\n\n"
        except asyncio.CancelledError:  # client disconnected
            return

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
