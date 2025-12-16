import json
import os
import asyncio
import hmac
import hashlib
import subprocess
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, Body, Request, HTTPException, Header, File, UploadFile
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from server.sync import router as sync_router

# Load environment variables
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
PLAYERS_CSV = os.path.join(BASE_DIR, "players.csv")
VERSION_PATH = os.path.join(BASE_DIR, "version.json")
DEFAULT_VERSION = "1.0.4"

app = FastAPI(title="Bear Planner MVP")
app.include_router(sync_router)

# ============================================================
# 🔔 SSE BROADCAST SYSTEM (authoritative server push)
# ============================================================
busy_set: set[str] = set()
subscribers: set[asyncio.Queue] = set()


async def event_generator(queue: asyncio.Queue):
    """Generate server-sent events from queue."""
    try:
        while True:
            data = await queue.get()
            yield f"data: {json.dumps(data)}\n\n"
    except asyncio.CancelledError:
        pass


async def broadcast_config(config: dict):
    """Broadcast configuration update to all SSE subscribers."""
    payload = {
        "type": "config_update",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "busy": list(busy_set),
    }
    for queue in list(subscribers):
        await queue.put(payload)


@app.get("/api/stream")
async def stream(request: Request):
    """SSE endpoint for real-time configuration updates."""
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
    """Load configuration from JSON file."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    """Save configuration to JSON file."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


async def notify_config_updated():
    """Notify all clients that configuration has been updated."""
    config = load_config()
    await broadcast_config(config)


# ============================================================
# Routes
# ============================================================

@app.get("/", response_class=HTMLResponse)
def index():
    """Serve the main HTML page."""
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))


@app.get("/api/map")
def get_map():
    """Get map configuration and entities."""
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


@app.get("/api/version")
def get_version():
    """Get application version."""
    try:
        with open(VERSION_PATH, "r", encoding="utf-8") as f:
            version_data = json.load(f)
        return version_data
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return {"version": DEFAULT_VERSION}


# ============================================================
# Castle Management
# ============================================================

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
    """Update a single castle's fields.

    Args:
        payload: Dictionary containing castle id and fields to update.

    Returns:
        Dictionary with status and castle id.

    Raises:
        HTTPException: If castle not found or validation fails.
    """
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


@app.post("/api/castles/bulk_update")
async def bulk_update_castles(payload: Dict[str, Any] = Body(...)):
    """Update multiple castles with the same field values.

    Args:
        payload: Dictionary containing:
            - ids: List of castle IDs to update
            - updates: Dictionary of field names and values to apply

    Returns:
        Dictionary with status, count of updated castles, and list of IDs.

    Raises:
        HTTPException: If validation fails or no valid updates provided.
    """
    if "ids" not in payload or not isinstance(payload["ids"], list):
        raise HTTPException(400, "Missing or invalid 'ids' field")

    if "updates" not in payload or not isinstance(payload["updates"], dict):
        raise HTTPException(400, "Missing or invalid 'updates' field")

    castle_ids = payload["ids"]
    updates = payload["updates"]

    if not castle_ids:
        raise HTTPException(400, "No castle IDs provided")

    if not updates:
        raise HTTPException(400, "No updates provided")

    # Validate that only allowed fields are being updated
    for key in updates.keys():
        if key not in ALLOWED_CASTLE_FIELDS and key != "locked":
            raise HTTPException(400, f"Illegal field: {key}")

    # Validate preference if provided
    if ("preference" in updates and
            updates["preference"] not in VALID_PREFERENCES):
        raise HTTPException(400, "Invalid preference")

    config = load_config()
    castles = config.get("castles", [])

    # Find castles to update
    updated_ids = []
    not_found_ids = []

    for castle_id in castle_ids:
        castle = next((c for c in castles if c.get("id") == castle_id), None)
        if not castle:
            not_found_ids.append(castle_id)
            continue

        # Apply updates to this castle
        for key, value in updates.items():
            if key == "player":
                castle["player"] = sanitise_player_name(str(value))
            elif key == "preference":
                castle["preference"] = value
            elif key == "attendance":
                castle[key] = sanitise_int(value, allow_none=True)
            elif key == "locked":
                # Special handling for locked field (boolean)
                if not isinstance(value, bool):
                    raise HTTPException(400, "Invalid locked value")
                castle[key] = value
            else:
                castle[key] = sanitise_int(value)

        updated_ids.append(castle_id)

    if not updated_ids:
        raise HTTPException(404, "No castles found to update")

    save_config(config)
    await notify_config_updated()

    result = {
        "status": "ok",
        "updated_count": len(updated_ids),
        "updated_ids": updated_ids,
    }

    if not_found_ids:
        result["not_found_ids"] = not_found_ids

    return result


# ============================================================
# Intent Handlers
# ============================================================

@app.post("/api/intent/move_castle")
async def move_castle(data: Dict[str, Any]):
    """Handle castle move intent."""
    entity_id = data.get("id")
    x = data.get("x")
    y = data.get("y")
    # Placeholder: print the information sent
    print(f"Received move_castle intent: id={entity_id}, x={x}, y={y}")
    # TODO: Implement castle move validation and placement, including:
    # - Check grid bounds (0 <= x < grid_size-1, 0 <= y < grid_size-1)
    # - Ensure no overlaps with other entities
    # - Validate permissions and busy state
    # - Update castle position in config
    # - Broadcast update via SSE
    # - Unmark busy
    return {"success": True}


@app.post("/api/intent/move_banner")
async def move_banner(data: Dict[str, Any]):
    """Handle banner move intent."""
    entity_id = data.get("id")
    x = data.get("x")
    y = data.get("y")
    # Placeholder: print the information sent
    print(f"Received move_banner intent: id={entity_id}, x={x}, y={y}")
    # TODO: Implement banner move validation and placement
    return {"success": True}


@app.post("/api/intent/move_bear_trap")
async def move_bear_trap(data: Dict[str, Any]):
    """Handle bear trap move intent."""
    entity_id = data.get("id")
    x = data.get("x")
    y = data.get("y")
    # Placeholder: print the information sent
    print(f"Received move_bear_trap intent: id={entity_id}, x={x}, y={y}")
    # TODO: Implement bear trap move validation and placement
    return {"success": True}


@app.post("/api/download_map_image")
async def download_map_image():
    """Download map as image (placeholder)."""
    print("Received download_map_image request")
    # TODO: Generate map image server-side
    return {"error": "Not implemented"}


@app.post("/api/auto_place_castles")
async def auto_place_castles():
    """Auto-place castles (placeholder)."""
    print("Received auto_place_castles request")
    # TODO: Auto-place castles server-side
    return {"success": True}


@app.post("/api/upload_csv")
async def upload_csv(csv_file: UploadFile = File(...)):
    """Upload castle data via CSV (placeholder)."""
    print(f"Received upload_csv: file={csv_file.filename}")
    # TODO: Read and parse CSV server-side
    return {"success": True}


@app.post("/api/intent/toggle_lock_castle")
async def toggle_lock_castle(data: Dict[str, Any]):
    """Toggle castle lock status."""
    entity_id = data.get("id")
    print(f"Received toggle_lock_castle intent: id={entity_id}")
    # TODO: Toggle castle lock, update config, broadcast SSE
    return {"success": True}


@app.post("/api/intent/toggle_lock_banner")
async def toggle_lock_banner(data: Dict[str, Any]):
    """Toggle banner lock status."""
    entity_id = data.get("id")
    print(f"Received toggle_lock_banner intent: id={entity_id}")
    # TODO: Toggle banner lock, update config, broadcast SSE
    return {"success": True}


@app.post("/api/intent/toggle_lock_bear_trap")
async def toggle_lock_bear_trap(data: Dict[str, Any]):
    """Toggle bear trap lock status."""
    entity_id = data.get("id")
    print(f"Received toggle_lock_bear_trap intent: id={entity_id}")
    # TODO: Toggle bear trap lock, update config, broadcast SSE
    return {"success": True}


@app.post("/api/intent/move_castle_away")
async def move_castle_away(data: Dict[str, Any]):
    """Move castle to edge position."""
    entity_id = data.get("id")
    print(f"Received move_castle_away intent: id={entity_id}")
    # TODO: Move castle to edge position, update config, broadcast SSE
    return {"success": True}


@app.post("/api/intent/mark_busy")
async def mark_busy(data: Dict[str, Any]):
    """Mark entity as busy."""
    entity_id = data.get("id")
    if not entity_id:
        raise HTTPException(400, "Missing id")
    busy_set.add(entity_id)
    await broadcast_config(load_config())
    return {"success": True}


@app.post("/api/intent/unmark_busy")
async def unmark_busy(data: Dict[str, Any]):
    """Unmark entity as busy."""
    entity_id = data.get("id")
    if not entity_id:
        raise HTTPException(400, "Missing id")
    busy_set.discard(entity_id)
    await broadcast_config(load_config())
    return {"success": True}


@app.post("/api/castles/add")
async def add_castle():
    """Add a new castle."""
    config = load_config()
    castles = config.get("castles", [])
    new_id = max((c.get("id", 0) for c in castles), default=0) + 1
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


@app.post("/api/bear_traps/add")
async def add_bear_trap():
    """Add a new bear trap."""
    config = load_config()
    bear_traps = config.get('bear_traps', [])
    new_id = f"B{max(len(bear_traps), 0) + 1}"
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
    """Delete a castle."""
    config = load_config()
    castle_id = data.get("id")
    config["castles"] = [
        c for c in config["castles"] if c.get("id") != castle_id
    ]
    save_config(config)

    reason = data.get("reason", "No reason provided")
    print(f"Deleted castle {castle_id} - Reason: {reason}")

    await notify_config_updated()
    return {"success": True}

# ============================================================
# GitHub Webhook Handler
# ============================================================

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
UPDATE_SCRIPT_PATH = os.path.join(BASE_DIR, "scripts", "update_and_restart.sh")


def verify_webhook_signature(payload_body: bytes,
                             signature_header: str) -> bool:
    """Verify the GitHub webhook signature using HMAC-SHA256."""
    if not WEBHOOK_SECRET:
        return False

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    hash_object = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()

    return hmac.compare_digest(expected_signature, signature_header)


async def trigger_update():
    """Trigger the update script in the background."""
    try:
        # Validate the update script exists and is executable
        if not os.path.isfile(UPDATE_SCRIPT_PATH):
            msg = f"Error: Update script not found at {UPDATE_SCRIPT_PATH}"
            print(msg)
            return

        if not os.access(UPDATE_SCRIPT_PATH, os.X_OK):
            msg = f"Error: Update script not executable: {UPDATE_SCRIPT_PATH}"
            print(msg)
            return

        # Run the update script in the background
        subprocess.Popen(
            [UPDATE_SCRIPT_PATH],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        print(f"Update script triggered: {UPDATE_SCRIPT_PATH}")
    except Exception as e:
        print(f"Error triggering update script: {e}")


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None)
):
    """Handle GitHub webhook events and trigger updates on push to main."""
    # Read the raw payload
    payload_body = await request.body()

    # Verify the webhook signature
    if not verify_webhook_signature(payload_body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse the JSON payload
    try:
        payload = json.loads(payload_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Check if this is a push event to the main branch
    if x_github_event == "push":
        ref = payload.get("ref", "")
        if ref == "refs/heads/main":
            print("Received push event to main branch")
            # Trigger update in background
            asyncio.create_task(trigger_update())
            return {
                "status": "success",
                "message": "Update triggered for main branch"
            }

    # For other events, just acknowledge receipt
    msg = f"Event {x_github_event} received but not processed"
    return {
        "status": "ok",
        "message": msg
    }

# ============================================================
# Static files
# ============================================================

app.mount("/static", StaticFiles(directory="static"), name="static")
