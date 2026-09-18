"""Flux Server-Sent Events global du dashboard."""

from __future__ import annotations

import asyncio
import json
import queue

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from app.core.realtime import RealtimeEvent, realtime_bus

router = APIRouter()
HEARTBEAT_SECONDS = 15.0


def _encode(event: RealtimeEvent) -> str:
    payload = json.dumps(event.as_dict(), ensure_ascii=False, separators=(",", ":"))
    return f"id: {event.id}\nevent: message\ndata: {payload}\n\n"


@router.get("/events")
async def events(
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    """Connexion unique, avec replay après reconnexion et heartbeat serveur."""
    try:
        cursor = int(last_event_id) if last_event_id is not None else None
    except ValueError:
        cursor = None
    subscription = realtime_bus.subscribe(cursor)

    async def stream():
        try:
            realtime_bus.publish("system.connected", data={"connected": True})
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.to_thread(
                        subscription.events.get, True, HEARTBEAT_SECONDS
                    )
                except queue.Empty:
                    yield ": heartbeat\n\n"
                    continue
                yield _encode(event)
        finally:
            realtime_bus.unsubscribe(subscription)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
