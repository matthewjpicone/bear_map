import json
import os
import asyncio
from datetime import datetime

from fastapi import FastAPI, Body, Request
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from server.sync import router as sync_router

# Load environment variables from .env file
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
PLAYERS_CSV = os.path.join(BASE_DIR, "players.csv")

app = FastAPI(title="Bear Planner MVP")
app.include_router(sync_router)

# ============================================================
# 🔔 SSE BROADCAST SYSTEM (authoritative server push)
# ============================================================
# Add after subscribers set
busy_set: set[str] = set()

# Update broadcast_config to include busy
async def broadcast_config(config: dict):
    payload = {
        "type": "config_update",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "busy": list(busy_set),  # Include busy IDs
    }
    for queue in list(subscribers):
        await queue.put(payload)

subscribers: set[asyncio.Queue] = set()

async def event_generator(queue: asyncio.Queue):
    try:
        while True:
            data = await queue.get()
            yield f"data: {json.dumps(data)}\n\n"
    except asyncio.CancelledError:
        pass

async def broadcast_config(config: dict):
    payload = {
        "type": "config_update",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    for queue in list(subscribers):
        await queue.put(payload)

@app.get("/api/stream")
async def stream(request: Request):
    queue = asyncio.Queue()
    subscribers.add(queue)

    async def cleanup():
        subscribers.discard(queue)

    request.state._cleanup = cleanup

    return StreamingResponse(
        event_generator(queue),
        media_type="text/event-stream"
    )

# ============================================================
# Helpers
# ============================================================

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

async def notify_config_updated():
    config = load_config()
    await broadcast_config(config)

# ============================================================
# Routes
# ============================================================

@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))

@app.get("/api/map")
def get_map():
    config = load_config()
    return {
        "grid_size": config["grid_size"],

        # visual + logic config
        "efficiency_scale": config["efficiency_scale"],

        # entities (authoritative)
        "banners": config.get("banners", []),
        "bear_traps": config.get("bear_traps", []),
        "castles": config.get("castles", [])
    }

from fastapi import APIRouter, HTTPException, Body
from typing import Any, Dict
import re



ALLOWED_CASTLE_FIELDS = {
    "player": str,
    "power": int,
    "player_level": int,
    "command_centre_level": int,
    "attendance": (int, type(None)),
    "rallies_30min": int,
    "preference": str,
}

VALID_PREFERENCES = {"Bear 1", "Bear 2", "Both"}

MAX_PLAYER_NAME_LEN = 32


def sanitise_player_name(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if len(value) > MAX_PLAYER_NAME_LEN:
        raise HTTPException(400, "Player name too long")
    return value


def sanitise_int(value: Any, *, allow_none=False) -> int | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool):
        raise HTTPException(400, "Invalid numeric value")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise HTTPException(400, "Invalid numeric value")


@app.post("/api/castles/update")
async def update_castle(payload: Dict[str, Any] = Body(...)):
    if "id" not in payload:
        raise HTTPException(400, "Missing castle id")

    castle_id = payload["id"]

    config = load_config()
    castles = config.get("castles", [])

    castle = next((c for c in castles if c.get("id") == castle_id), None)
    if not castle:
        raise HTTPException(404, f"Castle '{castle_id}' not found")

    updated = False

    for key, value in payload.items():
        if key == "id":
            continue

        if key not in ALLOWED_CASTLE_FIELDS:
            raise HTTPException(400, f"Illegal field: {key}")

        if key == "player":
            castle["player"] = sanitise_player_name(str(value))
        elif key == "preference":
            if value not in VALID_PREFERENCES:
                raise HTTPException(400, "Invalid preference")
            castle["preference"] = value
        elif key == "attendance":
            castle[key] = sanitise_int(value, allow_none=True)
        else:
            castle[key] = sanitise_int(value)

        updated = True

    if not updated:
        raise HTTPException(400, "No valid fields supplied")

    save_config(config)

    # ✅ THIS is now safe
    await notify_config_updated()

    return {
        "status": "ok",
        "id": castle_id,
    }

@app.post("/api/intent/move_castle")
async def move_castle(data: Dict[str, Any]):
    entity_id = data.get("id")
    x = data.get("x")
    y = data.get("y")
    print(f"Received move_castle intent: id={entity_id}, x={x}, y={y}")  # Placeholder: print the information sent
    # TODO: Implement castle move validation and placement, including:
    # - Check grid bounds (0 <= x < grid_size-1, 0 <= y < grid_size-1 for 2x2)
    # - Ensure no overlaps with other entities
    # - Validate permissions and busy state
    # - Update castle position in config
    # - Broadcast update via SSE
    # - Unmark busy
    return {"success": True}

@app.post("/api/intent/move_banner")
async def move_banner(data: Dict[str, Any]):
    entity_id = data.get("id")
    x = data.get("x")
    y = data.get("y")
    print(f"Received move_banner intent: id={entity_id}, x={x}, y={y}")  # Placeholder: print the information sent
    # TODO: Implement banner move validation and placement, including:
    # - Check grid bounds (0 <= x < grid_size, 0 <= y < grid_size)
    # - Ensure no overlaps (if applicable)
    # - Validate permissions and busy state
    # - Update banner position in config
    # - Broadcast update via SSE
    # - Unmark busy
    return {"success": True}

@app.post("/api/intent/move_bear_trap")
async def move_bear_trap(data: Dict[str, Any]):
    entity_id = data.get("id")
    x = data.get("x")
    y = data.get("y")
    print(f"Received move_bear_trap intent: id={entity_id}, x={x}, y={y}")  # Placeholder: print the information sent
    # TODO: Implement bear trap move validation and placement, including:
    # - Check grid bounds (0 <= x < grid_size, 0 <= y < grid_size)
    # - Ensure no overlaps with other bear traps/castles
    # - Validate permissions and busy state
    # - Update bear trap position in config
    # - Broadcast update via SSE
    # - Unmark busy
    return {"success": True}

from fastapi import UploadFile, File

@app.post("/api/download_map_image")
async def download_map_image():
    print("Received download_map_image request")  # Placeholder: print the information sent
    # TODO: Generate map image server-side (e.g., render canvas equivalent or use a library), return as image blob
    # For now, return a dummy image or error
    return {"error": "Not implemented"}

@app.post("/api/auto_place_castles")
async def auto_place_castles():
    print("Received auto_place_castles request")  # Placeholder: print the information sent
    # TODO: Auto-place castles server-side (algorithm to position them optimally), update config, recompute priorities, broadcast via SSE
    return {"success": True}

@app.post("/api/upload_csv")
async def upload_csv(csv_file: UploadFile = File(...)):
    print(f"Received upload_csv: file={csv_file.filename}")  # Placeholder: print the information sent
    # TODO: Read and parse CSV server-side, merge into current castles, recompute priorities, update config, broadcast via SSE
    return {"success": True}

# Added missing endpoints
@app.post("/api/intent/toggle_lock_castle")
async def toggle_lock_castle(data: Dict[str, Any]):
    entity_id = data.get("id")
    print(f"Received toggle_lock_castle intent: id={entity_id}")  # Placeholder: print the information sent
    # TODO: Toggle castle lock, update config, broadcast SSE
    return {"success": True}

@app.post("/api/intent/toggle_lock_banner")
async def toggle_lock_banner(data: Dict[str, Any]):
    entity_id = data.get("id")
    print(f"Received toggle_lock_banner intent: id={entity_id}")  # Placeholder: print the information sent
    # TODO: Toggle banner lock, update config, broadcast SSE
    return {"success": True}

@app.post("/api/intent/toggle_lock_bear_trap")
async def toggle_lock_bear_trap(data: Dict[str, Any]):
    entity_id = data.get("id")
    print(f"Received toggle_lock_bear_trap intent: id={entity_id}")  # Placeholder: print the information sent
    # TODO: Toggle bear trap lock, update config, broadcast SSE
    return {"success": True}

@app.post("/api/intent/move_castle_away")
async def move_castle_away(data: Dict[str, Any]):
    entity_id = data.get("id")
    print(f"Received move_castle_away intent: id={entity_id}")  # Placeholder: print the information sent
    # TODO: Move castle to edge position, update config, broadcast SSE
    return {"success": True}

# Add after the existing intent routes
@app.post("/api/intent/mark_busy")
async def mark_busy(data: Dict[str, Any]):
    entity_id = data.get("id")
    if not entity_id:
        raise HTTPException(400, "Missing id")
    busy_set.add(entity_id)
    await broadcast_config(load_config())  # Broadcast with busy
    return {"success": True}

@app.post("/api/intent/unmark_busy")
async def unmark_busy(data: Dict[str, Any]):
    entity_id = data.get("id")
    if not entity_id:
        raise HTTPException(400, "Missing id")
    busy_set.discard(entity_id)
    await broadcast_config(load_config())  # Broadcast with busy
    return {"success": True}

@app.post("/api/castles/add")
async def add_castle():
    config = load_config()
    new_id = max((c.get("id", 0) for c in config.get("castles", [])), default=0) + 1
    config["castles"].append({
        "id": new_id,
        "player": "",
        "power": 0,
        "player_level": 0,
        "command_centre_level": 0,
        "attendance": 0,
        "rallies_30min": 0,
        "preference": "Both",
        "locked": False,
        "priority": None,
        "efficiency": None,
        "round_trip": "NA",
        "last_updated": None,
        "x": None,
        "y": None
    })
    save_config(config)
    await notify_config_updated()
    return {"success": True, "id": new_id}

@app.post("/api/castles/delete")
async def delete_castle(data: Dict[str, Any]):
    config = load_config()
    config["castles"] = [c for c in config["castles"] if c.get("id") != data.get("id")]
    save_config(config)
    await notify_config_updated()
    return {"success": True}

@app.post("/api/bear_traps/add")
async def add_bear_trap():
    config = load_config()
    new_id = f"B{max(len(config.get('bear_traps', [])), 0) + 1}"
    config["bear_traps"].append({
        "id": new_id,
        "locked": False,
        "x": None,
        "y": None
    })
    save_config(config)
    await notify_config_updated()
    return {"success": True, "id": new_id}


@app.post("/api/castles/delete")
async def delete_castle(data: Dict[str, Any]):
    config = load_config()
    config["castles"] = [c for c in config["castles"] if c.get("id") != data.get("id")]
    save_config(config)

    reason = data.get("reason", "No reason provided")
    print(f"Deleted castle {data.get('id')} - Reason: {reason}")  # Log to console/server logs

    await notify_config_updated()
    return {"success": True}

# ============================================================
# Discord Integration
# ============================================================

from server.discord_integration import get_discord_client

@app.get("/api/discord/status")
async def get_discord_status():
    """Get Discord connection status and current configuration."""
    config = load_config()
    discord_config = config.get("discord", {})
    
    client = await get_discord_client()
    connected = client.is_connected() if client else False
    
    return {
        "connected": connected,
        "enabled": discord_config.get("enabled", False),
        "channel_id": discord_config.get("channel_id"),
        "channel_name": discord_config.get("channel_name"),
        "linked_at": discord_config.get("linked_at"),
        "bot_token_configured": os.getenv("DISCORD_BOT_TOKEN") is not None,
    }

@app.post("/api/discord/link")
async def link_discord_channel(data: Dict[str, Any]):
    """
    Link a Discord channel or thread to the workspace.
    
    Request body:
        channel_id: Discord channel or thread ID (as string or int)
    """
    channel_id_str = data.get("channel_id")
    if not channel_id_str:
        raise HTTPException(400, "channel_id is required")
    
    try:
        channel_id = int(channel_id_str)
    except (TypeError, ValueError):
        raise HTTPException(400, "channel_id must be a valid number")
    
    # Get Discord client
    client = await get_discord_client()
    if not client:
        raise HTTPException(503, "Discord bot token not configured. Set DISCORD_BOT_TOKEN environment variable.")
    
    if not client.is_connected():
        raise HTTPException(503, "Discord client is not connected")
    
    # Get channel info to verify it exists and is accessible
    channel_info = await client.get_channel_info(channel_id)
    if not channel_info:
        raise HTTPException(404, "Channel not found or bot does not have access")
    
    # Update config
    config = load_config()
    config["discord"] = {
        "enabled": True,
        "channel_id": str(channel_id),
        "channel_name": channel_info.get("name"),
        "linked_at": datetime.now().isoformat(),
    }
    save_config(config)
    
    await notify_config_updated()
    
    return {
        "success": True,
        "channel": channel_info,
    }

@app.post("/api/discord/unlink")
async def unlink_discord_channel():
    """Unlink the Discord channel from the workspace."""
    config = load_config()
    config["discord"] = {
        "enabled": False,
        "channel_id": None,
        "channel_name": None,
        "linked_at": None,
    }
    save_config(config)
    
    await notify_config_updated()
    
    return {"success": True}

@app.get("/api/discord/messages")
async def get_discord_messages(limit: int = 50):
    """
    Fetch messages from the linked Discord channel.
    
    Query params:
        limit: Maximum number of messages to fetch (default: 50, max: 100)
    """
    config = load_config()
    discord_config = config.get("discord", {})
    
    if not discord_config.get("enabled"):
        raise HTTPException(400, "Discord is not enabled")
    
    channel_id_str = discord_config.get("channel_id")
    if not channel_id_str:
        raise HTTPException(400, "No channel linked")
    
    try:
        channel_id = int(channel_id_str)
    except (TypeError, ValueError):
        raise HTTPException(500, "Invalid channel_id in configuration")
    
    # Get Discord client
    client = await get_discord_client()
    if not client:
        raise HTTPException(503, "Discord bot token not configured")
    
    if not client.is_connected():
        raise HTTPException(503, "Discord client is not connected")
    
    # Fetch messages
    limit = min(max(1, limit), 100)  # Clamp between 1 and 100
    messages = await client.fetch_messages(channel_id, limit)
    
    return {
        "messages": messages,
        "count": len(messages),
        "channel_id": channel_id_str,
        "channel_name": discord_config.get("channel_name"),
    }

# ============================================================
# Static files
# ============================================================

app.mount("/static", StaticFiles(directory="static"), name="static")
