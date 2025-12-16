import json
import os
import asyncio
import hmac
import hashlib
import subprocess
from datetime import datetime

from fastapi import FastAPI, Body, Request, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from server.sync import router as sync_router
from database import init_db
from audit_service import AuditLogger
from user_context import get_current_user

# Load environment variables
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
PLAYERS_CSV = os.path.join(BASE_DIR, "players.csv")
VERSION_PATH = os.path.join(BASE_DIR, "version.json")
DEFAULT_VERSION = "1.0.4"

app = FastAPI(title="Bear Planner MVP")
app.include_router(sync_router)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()

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

@app.get("/api/version")
def get_version():
    try:
        with open(VERSION_PATH, "r", encoding="utf-8") as f:
            version_data = json.load(f)
        return version_data
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return {"version": DEFAULT_VERSION}

from fastapi import APIRouter, HTTPException, Body
from typing import Any, Dict, Optional
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
async def update_castle(
    payload: Dict[str, Any] = Body(...),
    user: str = Depends(get_current_user)
):
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

        # Store old value for audit log
        old_value = castle.get(key)

        if key == "player":
            new_value = sanitise_player_name(str(value))
            castle["player"] = new_value
        elif key == "preference":
            if value not in VALID_PREFERENCES:
                raise HTTPException(400, "Invalid preference")
            new_value = value
            castle["preference"] = value
        elif key == "attendance":
            new_value = sanitise_int(value, allow_none=True)
            castle[key] = new_value
        else:
            new_value = sanitise_int(value)
            castle[key] = new_value

        # Log the update
        AuditLogger.log_update(
            user=user,
            entity_type="castle",
            entity_id=str(castle_id),
            field_name=key,
            before_value=old_value,
            after_value=new_value,
        )

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
async def add_castle(user: str = Depends(get_current_user)):
    config = load_config()
    # Extract numeric IDs from castle IDs like "Castle 9"
    existing_ids = []
    for c in config.get("castles", []):
        castle_id = c.get("id", "")
        if isinstance(castle_id, str) and castle_id.startswith("Castle "):
            try:
                existing_ids.append(int(castle_id.replace("Castle ", "")))
            except ValueError:
                pass
    new_num = max(existing_ids, default=0) + 1
    new_id = f"Castle {new_num}"
    new_castle = {
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
    }
    config["castles"].append(new_castle)
    save_config(config)

    # Log the creation
    AuditLogger.log_create(
        user=user,
        entity_type="castle",
        entity_id=str(new_id),
        after_value=new_castle,
    )

    await notify_config_updated()
    return {"success": True, "id": new_id}

@app.post("/api/bear_traps/add")
async def add_bear_trap(user: str = Depends(get_current_user)):
    config = load_config()
    new_id = f"B{max(len(config.get('bear_traps', [])), 0) + 1}"
    new_trap = {
        "id": new_id,
        "locked": False,
        "x": None,
        "y": None
    }
    config["bear_traps"].append(new_trap)
    save_config(config)

    # Log the creation
    AuditLogger.log_create(
        user=user,
        entity_type="bear_trap",
        entity_id=new_id,
        after_value=new_trap,
    )

    await notify_config_updated()
    return {"success": True, "id": new_id}


@app.post("/api/castles/delete")
async def delete_castle(data: Dict[str, Any], user: str = Depends(get_current_user)):
    config = load_config()
    castle_id = data.get("id")

    # Find the castle before deletion for audit log
    castle = next((c for c in config["castles"] if c.get("id") == castle_id), None)

    config["castles"] = [c for c in config["castles"] if c.get("id") != castle_id]
    save_config(config)

    reason = data.get("reason", "No reason provided")
    print(f"Deleted castle {castle_id} - Reason: {reason}")  # Log to console/server logs

    # Log the deletion
    if castle:
        AuditLogger.log_delete(
            user=user,
            entity_type="castle",
            entity_id=str(castle_id),
            before_value=castle,
            description=f"Deleted castle {castle_id} - Reason: {reason}",
        )

    await notify_config_updated()
    return {"success": True}

# ============================================================
# GitHub Webhook Handler
# ============================================================

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
UPDATE_SCRIPT_PATH = os.path.join(BASE_DIR, "scripts", "update_and_restart.sh")

def verify_webhook_signature(payload_body: bytes, signature_header: str) -> bool:
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
            print(f"Error: Update script not found at {UPDATE_SCRIPT_PATH}")
            return
        
        if not os.access(UPDATE_SCRIPT_PATH, os.X_OK):
            print(f"Error: Update script is not executable: {UPDATE_SCRIPT_PATH}")
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
    """
    Handle GitHub webhook events.
    Validates the payload signature and triggers updates on push to main branch.
    """
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
            print(f"Received push event to main branch")
            # Trigger update in background
            asyncio.create_task(trigger_update())
            return {
                "status": "success",
                "message": "Update triggered for main branch"
            }
    
    # For other events, just acknowledge receipt
    return {
        "status": "ok",
        "message": f"Event {x_github_event} received but not processed"
    }

# ============================================================
# Audit Log Endpoints
# ============================================================

@app.get("/api/audit/logs")
async def get_audit_logs(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    user: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """Get audit logs with optional filtering.

    Args:
        entity_type: Filter by entity type (castle, bear_trap, banner, settings).
        entity_id: Filter by specific entity ID.
        user: Filter by user who made changes.
        limit: Maximum number of logs to return (default 100).
        offset: Number of logs to skip (default 0).

    Returns:
        List of audit log entries.
    """
    logs = AuditLogger.get_logs(
        entity_type=entity_type,
        entity_id=entity_id,
        user=user,
        limit=limit,
        offset=offset,
    )
    return {"logs": logs, "count": len(logs)}


@app.get("/api/audit/entity/{entity_type}/{entity_id}")
async def get_entity_audit_history(entity_type: str, entity_id: str, limit: int = 50):
    """Get complete audit history for a specific entity.

    Args:
        entity_type: Type of entity (castle, bear_trap, banner, settings).
        entity_id: ID of the entity.
        limit: Maximum number of logs to return (default 50).

    Returns:
        List of audit log entries for the entity.
    """
    logs = AuditLogger.get_entity_history(
        entity_type=entity_type, entity_id=entity_id, limit=limit
    )
    return {"entity_type": entity_type, "entity_id": entity_id, "logs": logs}


@app.get("/api/audit/export")
async def export_audit_logs(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    user: Optional[str] = None,
):
    """Export audit logs as CSV.

    Args:
        entity_type: Filter by entity type.
        entity_id: Filter by specific entity ID.
        user: Filter by user who made changes.

    Returns:
        CSV file with audit logs.
    """
    csv_content = AuditLogger.export_logs_csv(
        entity_type=entity_type, entity_id=entity_id, user=user
    )
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )


# ============================================================
# Static files
# ============================================================

app.mount("/static", StaticFiles(directory="static"), name="static")
