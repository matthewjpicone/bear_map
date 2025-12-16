import json
import os
import asyncio
import hmac
import hashlib
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import FastAPI, Body, Request, HTTPException, Header, Depends, Query
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from server.sync import router as sync_router
from server.auth import (
    WorkspaceManager,
    get_current_user,
    require_authentication,
    create_access_token,
    get_user_workspace_filter,
)
from server.discord_oauth import (
    get_discord_oauth_url,
    authenticate_discord_user,
    is_discord_oauth_configured,
)

# Load environment variables
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
PLAYERS_CSV = os.path.join(BASE_DIR, "players.csv")
VERSION_PATH = os.path.join(BASE_DIR, "version.json")
DEFAULT_VERSION = "1.0.4"

app = FastAPI(title="Bear Planner MVP")
app.include_router(sync_router)

# Initialize workspace manager
workspace_manager = WorkspaceManager(CONFIG_PATH)

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
def get_map(
    workspace_id: Optional[str] = Query(None),
    user: Optional[dict] = Depends(get_current_user),
):
    """Get map data, optionally filtered by workspace.

    Args:
        workspace_id: Optional workspace filter.
        user: Current authenticated user (optional).

    Returns:
        Map configuration and entities.
    """
    config = load_config()
    global_settings = config.get("global_settings", {})
    auth_enabled = global_settings.get("auth_enabled", False)

    # Determine workspace filter
    workspace_filter = None
    if auth_enabled and user:
        user_workspaces = get_user_workspace_filter(user)
        if workspace_id:
            # Verify user has access to requested workspace
            if workspace_id not in user_workspaces:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied to workspace: {workspace_id}",
                )
            workspace_filter = {workspace_id}
        else:
            workspace_filter = user_workspaces

    # Filter entities by workspace
    def filter_entities(entities):
        if not workspace_filter:
            return entities
        return [
            e
            for e in entities
            if e.get("workspace_id") in workspace_filter
        ]

    return {
        "grid_size": config["grid_size"],
        "efficiency_scale": config["efficiency_scale"],
        "banners": filter_entities(config.get("banners", [])),
        "bear_traps": filter_entities(config.get("bear_traps", [])),
        "castles": filter_entities(config.get("castles", [])),
        "workspace_id": workspace_id,
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
async def update_castle(
    payload: Dict[str, Any] = Body(...),
    user: Optional[dict] = Depends(get_current_user),
):
    """Update castle data with workspace access control.

    Args:
        payload: Castle update data.
        user: Current authenticated user (optional).

    Returns:
        Update status.

    Raises:
        HTTPException: If castle not found or access denied.
    """
    if "id" not in payload:
        raise HTTPException(400, "Missing castle id")

    castle_id = payload["id"]

    config = load_config()
    global_settings = config.get("global_settings", {})
    auth_enabled = global_settings.get("auth_enabled", False)
    castles = config.get("castles", [])

    castle = next((c for c in castles if c.get("id") == castle_id), None)
    if not castle:
        raise HTTPException(404, f"Castle '{castle_id}' not found")

    # Check workspace access
    if auth_enabled and user:
        castle_workspace = castle.get("workspace_id")
        user_workspaces = set(user.get("workspaces", []))
        if castle_workspace not in user_workspaces:
            raise HTTPException(
                403, f"Access denied to castle in workspace: {castle_workspace}"
            )

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
async def add_castle(
    workspace_id: str = Query("default"),
    user: Optional[dict] = Depends(get_current_user),
):
    """Add a new castle to a workspace.

    Args:
        workspace_id: Target workspace ID.
        user: Current authenticated user (optional).

    Returns:
        Success status and new castle ID.

    Raises:
        HTTPException: If access denied to workspace.
    """
    config = load_config()
    global_settings = config.get("global_settings", {})
    auth_enabled = global_settings.get("auth_enabled", False)

    # Check workspace access
    if auth_enabled and user:
        user_workspaces = set(user.get("workspaces", []))
        if workspace_id not in user_workspaces:
            raise HTTPException(403, f"Access denied to workspace: {workspace_id}")

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
        "y": None,
        "workspace_id": workspace_id,
    })
    save_config(config)
    await notify_config_updated()
    return {"success": True, "id": new_id}


@app.post("/api/bear_traps/add")
async def add_bear_trap(
    workspace_id: str = Query("default"),
    user: Optional[dict] = Depends(get_current_user),
):
    """Add a new bear trap to a workspace.

    Args:
        workspace_id: Target workspace ID.
        user: Current authenticated user (optional).

    Returns:
        Success status and new bear trap ID.

    Raises:
        HTTPException: If access denied to workspace.
    """
    config = load_config()
    global_settings = config.get("global_settings", {})
    auth_enabled = global_settings.get("auth_enabled", False)

    # Check workspace access
    if auth_enabled and user:
        user_workspaces = set(user.get("workspaces", []))
        if workspace_id not in user_workspaces:
            raise HTTPException(403, f"Access denied to workspace: {workspace_id}")

    new_id = f"B{max(len(config.get('bear_traps', [])), 0) + 1}"
    config["bear_traps"].append({
        "id": new_id,
        "locked": False,
        "x": None,
        "y": None,
        "workspace_id": workspace_id,
    })
    save_config(config)
    await notify_config_updated()
    return {"success": True, "id": new_id}


@app.post("/api/castles/delete")
async def delete_castle(
    data: Dict[str, Any],
    user: Optional[dict] = Depends(get_current_user),
):
    """Delete a castle with workspace access control.

    Args:
        data: Delete request data with castle ID.
        user: Current authenticated user (optional).

    Returns:
        Success status.

    Raises:
        HTTPException: If castle not found or access denied.
    """
    config = load_config()
    global_settings = config.get("global_settings", {})
    auth_enabled = global_settings.get("auth_enabled", False)

    castle_id = data.get("id")
    castle = next((c for c in config["castles"] if c.get("id") == castle_id), None)

    if not castle:
        raise HTTPException(404, f"Castle '{castle_id}' not found")

    # Check workspace access
    if auth_enabled and user:
        castle_workspace = castle.get("workspace_id")
        user_workspaces = set(user.get("workspaces", []))
        if castle_workspace not in user_workspaces:
            raise HTTPException(403, f"Access denied to workspace: {castle_workspace}")

    config["castles"] = [c for c in config["castles"] if c.get("id") != castle_id]
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
# Authentication & Workspace Routes
# ============================================================


@app.get("/api/auth/status")
async def auth_status(user: Optional[dict] = Depends(get_current_user)):
    """Get authentication status and user information.

    Args:
        user: Current authenticated user (optional).

    Returns:
        Authentication status and user details.
    """
    config = load_config()
    global_settings = config.get("global_settings", {})
    auth_enabled = global_settings.get("auth_enabled", False)

    if not auth_enabled:
        return {
            "authenticated": False,
            "auth_enabled": False,
            "message": "Authentication is disabled",
        }

    if not user:
        return {
            "authenticated": False,
            "auth_enabled": True,
            "discord_oauth_configured": is_discord_oauth_configured(),
        }

    return {
        "authenticated": True,
        "auth_enabled": True,
        "user": {
            "discord_id": user.get("discord_id"),
            "username": user.get("username"),
            "workspaces": user.get("workspaces", []),
        },
    }


@app.get("/api/auth/discord/url")
async def get_discord_login_url():
    """Get Discord OAuth login URL.

    Returns:
        Discord OAuth authorization URL.

    Raises:
        HTTPException: If Discord OAuth is not configured.
    """
    try:
        url = get_discord_oauth_url()
        return {"url": url}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/auth/discord/callback")
async def discord_callback(code: str = Query(...)):
    """Handle Discord OAuth callback.

    Args:
        code: Authorization code from Discord.

    Returns:
        JWT access token for the authenticated user.

    Raises:
        HTTPException: If authentication fails or user is not authorized.
    """
    try:
        # Authenticate with Discord
        discord_user_id, username = await authenticate_discord_user(code)

        # Get user's authorized workspaces
        user_workspaces = workspace_manager.get_user_workspaces(discord_user_id)

        if not user_workspaces:
            raise HTTPException(
                status_code=403,
                detail="User is not authorized for any workspace",
            )

        # Create access token
        token = create_access_token(discord_user_id, username, user_workspaces)

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "discord_id": discord_user_id,
                "username": username,
                "workspaces": list(user_workspaces),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


@app.get("/api/workspaces")
async def list_workspaces(user: Optional[dict] = Depends(get_current_user)):
    """List workspaces accessible to the current user.

    Args:
        user: Current authenticated user (optional).

    Returns:
        List of accessible workspaces.
    """
    config = load_config()
    global_settings = config.get("global_settings", {})
    auth_enabled = global_settings.get("auth_enabled", False)

    all_workspaces = config.get("workspaces", {})

    if not auth_enabled or not user:
        # Return all workspaces if auth is disabled or user is not authenticated
        return {
            "workspaces": [
                {
                    "id": ws_id,
                    "name": ws.get("name", ws_id),
                    "description": ws.get("description", ""),
                }
                for ws_id, ws in all_workspaces.items()
            ]
        }

    # Filter to user's accessible workspaces
    user_workspace_ids = set(user.get("workspaces", []))
    accessible = [
        {
            "id": ws_id,
            "name": ws.get("name", ws_id),
            "description": ws.get("description", ""),
        }
        for ws_id, ws in all_workspaces.items()
        if ws_id in user_workspace_ids
    ]

    return {"workspaces": accessible}


# ============================================================
# Static files
# ============================================================

app.mount("/static", StaticFiles(directory="static"), name="static")
