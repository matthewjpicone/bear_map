"""
Bear Map FastAPI Application

Main entry point for the Bear Map application, serving the REST API
and real-time collaborative bear trap planning interface.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
"""

import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from fastapi.responses import StreamingResponse

from server.sync import router as sync_router
from server.routes import router as routes_router
from server.castles import router as castles_router
from server.intents import router as intents_router
from server.webhook import router as webhook_router
from server.broadcast import subscribers

# Load environment variables
load_dotenv()

app = FastAPI(title="Bear Planner MVP")

# Include all routers
app.include_router(sync_router)
app.include_router(routes_router)
app.include_router(castles_router)
app.include_router(intents_router)
app.include_router(webhook_router)

# ============================================================
# SSE Endpoint
# ============================================================


@app.get("/api/stream")
async def stream(request: Request):
    """Server-Sent Events (SSE) endpoint for real-time updates.

    Clients connect to this endpoint to receive real-time configuration updates
    when entities are moved, locked, or busy states change.

    Args:
        request: FastAPI request object.

    Returns:
        StreamingResponse with text/event-stream content type.
    """
    from server.broadcast import event_generator

    queue = asyncio.Queue()
    subscribers.add(queue)

    async def cleanup():
        subscribers.discard(queue)

    request.state._cleanup = cleanup

    return StreamingResponse(event_generator(queue), media_type="text/event-stream")


# ============================================================
# Static Files
# ============================================================

app.mount("/static", StaticFiles(directory="static"), name="static")
