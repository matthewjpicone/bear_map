"""
Server-sent events (SSE) broadcasting module.

This module handles real-time updates via Server-Sent Events, managing
subscriber connections and broadcasting configuration updates to all clients.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
"""

import asyncio
import json
from datetime import datetime
from typing import Set

from fastapi.responses import StreamingResponse

# Global set of SSE subscribers (asyncio.Queue instances)
subscribers: Set[asyncio.Queue] = set()

# Global set of busy entity IDs
busy_set: Set[str] = set()


async def event_generator(queue: asyncio.Queue):
    """Generate SSE events from the queue.

    Args:
        queue: Async queue to read events from.

    Yields:
        SSE formatted event strings.
    """
    try:
        while True:
            data = await queue.get()
            yield f"data: {json.dumps(data)}\n\n"
    except asyncio.CancelledError:
        pass


async def broadcast_config(config: dict):
    """Broadcast configuration updates to all SSE subscribers.

    Args:
        config: Configuration dictionary (not used currently but kept for API consistency).
    """
    payload = {
        "type": "config_update",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "busy": list(busy_set),
    }
    for queue in list(subscribers):
        await queue.put(payload)


async def notify_config_updated():
    """Load config and broadcast update notification to all SSE subscribers."""
    from logic.config import load_config

    config = load_config()
    await broadcast_config(config)
