"""
WebSocket synchronization module.

This module handles real-time WebSocket connections for collaborative editing
with soft-locking mechanism to prevent conflicts.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
"""

# from fastapi import WebSocket, WebSocketDisconnect
# from fastapi import APIRouter
# import time
# import json
#
# router = APIRouter()
#
# clients = set()
# map_state = {
#     "castles": {},
#     "bears": {},
#     "version": 0
# }
#
# @router.websocket("/ws")
# async def websocket_endpoint(ws: WebSocket):
#     await ws.accept()
#     clients.add(ws)
#
#     # send full state on connect
#     await ws.send_json({
#         "type": "state_init",
#         "state": map_state
#     })
#
#     try:
#         while True:
#             msg = await ws.receive_json()
#
#             if msg["type"] == "batch_update":
#                 await apply_updates(msg["updates"], ws)
#
#             elif msg["type"] in ("busy", "release"):
#                 await broadcast({
#                     "type": msg["type"],
#                     "id": msg["id"]
#                 }, ws)
#
#     except WebSocketDisconnect:
#         clients.remove(ws)
#
# # async def apply_updates(updates, sender):
# #     global map_state
# #     now = int(time.time() * 1000)
# #
# #     accepted = []
# #
# #     for u in updates:
# #         obj_id = u["id"]
# #         bucket = "castles" if obj_id.startswith("Castle") else "bears"
# #
# #         current = map_state[bucket].get(obj_id)
# #         if current and current.get("updated_at", 0) > u["updated_at"]:
# #             continue
# #
# #         map_state[bucket][obj_id] = u
# #         accepted.append(u)
# #
# #     if accepted:
# #         map_state["version"] += 1
# #         await broadcast({
# #             "type": "updates",
# #             "updates": accepted
# #         }, sender)
#
# async def apply_updates(updates, sender):
#     global map_state
#
#     accepted = []
#
#     for u in updates:
#         obj_id = u.get("id")
#         if not obj_id:
#             continue
#
#         if obj_id.startswith("Castle"):
#             bucket = "castles"
#         elif obj_id.startswith("Bear"):
#             bucket = "bears"
#         else:
#             continue
#
#         current = map_state[bucket].get(obj_id)
#
#         # last-write-wins
#         if current and current.get("updated_at", 0) > u.get("updated_at", 0):
#             continue
#
#         map_state[bucket][obj_id] = u
#         accepted.append(u)
#
#     if accepted:
#         map_state["version"] += 1
#         await broadcast({
#             "type": "updates",
#             "updates": accepted
#         }, sender)
#
#
# async def broadcast(payload, sender):
#     dead = set()
#     for c in clients:
#         if c is sender:
#             continue
#         try:
#             await c.send_json(payload)
#         except:
#             dead.add(c)
#     for d in dead:
#         clients.remove(d)


import time

from fastapi import WebSocket, WebSocketDisconnect, APIRouter

router = APIRouter()

# ==========================
# Globals
# ==========================
clients: set[WebSocket] = set()

LOCK_TTL_MS = 20_000  # 20 seconds soft lock timeout

map_state = {
    "castles": {},
    "bears": {},
    "version": 0
}

# id -> { owner: WebSocket, expires_at: ms }
soft_locks: dict[str, dict] = {}


# ==========================
# Helpers
# ==========================
def now_ms() -> int:
    """Get current time in milliseconds since epoch.

    Returns:
        Current timestamp in milliseconds.
    """
    return int(time.time() * 1000)


def cleanup_expired_locks():
    """Remove all expired soft locks from the global locks dictionary.

    Checks all locks against the current timestamp and removes any that
    have exceeded their TTL.
    """
    t = now_ms()
    expired = [
        obj_id for obj_id, lock in soft_locks.items()
        if lock["expires_at"] <= t
    ]
    for obj_id in expired:
        del soft_locks[obj_id]


async def broadcast(payload, sender=None):
    """Broadcast a message to all connected WebSocket clients.

    Args:
        payload: JSON-serializable payload to send to clients.
        sender: Optional WebSocket connection to exclude from broadcast.
    """
    dead = set()
    for c in clients:
        if c is sender:
            continue
        try:
            await c.send_json(payload)
        except Exception:
            dead.add(c)

    for d in dead:
        clients.remove(d)


async def broadcast_lock_release(obj_id: str):
    """Broadcast a lock release message to all clients.

    Args:
        obj_id: ID of the entity whose lock was released.
    """
    await broadcast({
        "type": "release",
        "id": obj_id
    })


# ==========================
# State Updates
# ==========================
async def apply_updates(updates, sender):
    global map_state
    accepted = []

    for u in updates:
        obj_id = u.get("id")
        if not obj_id:
            continue

        bucket = (
            "castles" if obj_id.startswith("Castle")
            else "bears" if obj_id.startswith("Bear")
            else None
        )
        if not bucket:
            continue

        current = map_state[bucket].get(obj_id)

        # last-write-wins
        if current and current.get("updated_at", 0) > u.get("updated_at", 0):
            continue

        map_state[bucket][obj_id] = u
        accepted.append(u)

    if accepted:
        map_state["version"] += 1
        await broadcast({
            "type": "updates",
            "updates": accepted
        }, sender)


# ==========================
# WebSocket Endpoint
# ==========================
@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)

    # Send full state on connect
    await ws.send_json({
        "type": "state_init",
        "state": map_state
    })

    try:
        while True:
            cleanup_expired_locks()

            msg = await ws.receive_json()
            msg_type = msg.get("type")

            # --------------------------
            # DATA UPDATES
            # --------------------------
            if msg_type == "batch_update":
                await apply_updates(msg.get("updates", []), ws)

            # --------------------------
            # SOFT LOCK (BUSY)
            # --------------------------
            elif msg_type == "busy":
                obj_id = msg.get("id")
                if not obj_id:
                    continue

                cleanup_expired_locks()

                existing = soft_locks.get(obj_id)

                # Someone else owns a valid lock

                if existing and existing["owner"] is not ws:
                    continue

                # Acquire / refresh lock
                soft_locks[obj_id] = {
                    "owner": ws,
                    "expires_at": now_ms() + LOCK_TTL_MS
                }

                await broadcast({
                    "type": "busy",
                    "id": obj_id
                }, ws)

            # --------------------------
            # RELEASE LOCK
            # --------------------------
            elif msg_type == "release":
                obj_id = msg.get("id")
                if not obj_id:
                    continue

                lock = soft_locks.get(obj_id)
                if lock and lock["owner"] is ws:
                    del soft_locks[obj_id]
                    await broadcast_lock_release(obj_id)

    except WebSocketDisconnect:
        clients.remove(ws)

        # 🔥 Auto-release any locks owned by this client
        released = [
            obj_id for obj_id, lock in soft_locks.items()
            if lock["owner"] is ws
        ]

        for obj_id in released:
            del soft_locks[obj_id]
            await broadcast_lock_release(obj_id)
