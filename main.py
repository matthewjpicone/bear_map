import json
import os
import asyncio
import hmac
import hashlib
import subprocess
from datetime import datetime
from typing import Any, Dict

<<<<<<< HEAD
from fastapi import FastAPI, Body, Request, HTTPException, Header, UploadFile, File
=======
from fastapi import FastAPI, Body, Request, HTTPException, Header, File, UploadFile
>>>>>>> copilot/add-bulk-edit-castles-ui
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
<<<<<<< HEAD
subscribers: set[asyncio.Queue] = set()
busy_set: set[str] = set()

=======
busy_set: set[str] = set()
subscribers: set[asyncio.Queue] = set()
>>>>>>> copilot/add-bulk-edit-castles-ui


async def event_generator(queue: asyncio.Queue):
<<<<<<< HEAD
    """Generate SSE events from the queue.

    Args:
        queue: Async queue to read events from.

    Yields:
        SSE formatted event strings.
    """
=======
    """Generate server-sent events from queue."""
>>>>>>> copilot/add-bulk-edit-castles-ui
    try:
        while True:
            data = await queue.get()
            yield f"data: {json.dumps(data)}\n\n"
    except asyncio.CancelledError:
        pass


async def broadcast_config(config: dict):
<<<<<<< HEAD
    """Broadcast configuration updates to all SSE subscribers.

    Args:
        config: Configuration dictionary (not used currently but kept for API consistency).
    """
=======
    """Broadcast configuration update to all SSE subscribers."""
>>>>>>> copilot/add-bulk-edit-castles-ui
    payload = {
        "type": "config_update",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "busy": list(busy_set),
    }
    for queue in list(subscribers):
        await queue.put(payload)


@app.get("/api/stream")
async def stream(request: Request):
<<<<<<< HEAD
    """Server-Sent Events (SSE) endpoint for real-time updates.

    Clients connect to this endpoint to receive real-time configuration updates
    when entities are moved, locked, or busy states change.

    Args:
        request: FastAPI request object.

    Returns:
        StreamingResponse with text/event-stream content type.
    """
=======
    """SSE endpoint for real-time configuration updates."""
>>>>>>> copilot/add-bulk-edit-castles-ui
    queue = asyncio.Queue()
    subscribers.add(queue)

    async def cleanup():
        subscribers.discard(queue)

    request.state._cleanup = cleanup

    return StreamingResponse(event_generator(queue), media_type="text/event-stream")



# ============================================================
# Helpers
# ============================================================

<<<<<<< HEAD

def load_config() -> dict:
    """Load configuration from config.json.

    Returns:
        Configuration dictionary.
    """
=======
def load_config():
    """Load configuration from JSON file."""
>>>>>>> copilot/add-bulk-edit-castles-ui
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


<<<<<<< HEAD
def save_config(config: dict):
    """Save configuration to config.json.

    Args:
        config: Configuration dictionary to save.
    """
=======
def save_config(config):
    """Save configuration to JSON file."""
>>>>>>> copilot/add-bulk-edit-castles-ui
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


async def notify_config_updated():
<<<<<<< HEAD
    """Load config and broadcast update notification to all SSE subscribers."""
=======
    """Notify all clients that configuration has been updated."""
>>>>>>> copilot/add-bulk-edit-castles-ui
    config = load_config()
    await broadcast_config(config)


<<<<<<< HEAD
def is_within_bounds(
    x: int, y: int, grid_size: int, width: int = 1, height: int = 1
) -> bool:
    """Check if an entity at (x, y) with given dimensions is within grid bounds.

    Args:
        x: X coordinate.
        y: Y coordinate.
        grid_size: Size of the grid.
        width: Width of the entity (default 1).
        height: Height of the entity (default 1).

    Returns:
        True if entity is within bounds, False otherwise.
    """
    return 0 <= x <= grid_size - width and 0 <= y <= grid_size - height


def check_castle_overlap(
    x: int, y: int, castles: list, exclude_id: str = None
) -> tuple[bool, str | None]:
    """Check if a 2x2 castle at (x, y) overlaps with any other castle.

    Args:
        x: X coordinate of castle.
        y: Y coordinate of castle.
        castles: List of castle dictionaries.
        exclude_id: Castle ID to exclude from overlap check (for moving existing castle).

    Returns:
        Tuple of (has_overlap, overlapping_castle_id).
    """
    for castle in castles:
        if exclude_id and castle.get("id") == exclude_id:
            continue
        cx, cy = castle.get("x"), castle.get("y")
        if cx is None or cy is None:
            continue
        # Check if 2x2 rectangles overlap
        if not (x + 2 <= cx or cx + 2 <= x or y + 2 <= cy or cy + 2 <= y):
            return True, castle.get("id")
    return False, None


def check_bear_trap_overlap(
    x: int, y: int, bear_traps: list, castles: list, exclude_id: str = None
) -> tuple[bool, str | None]:
    """Check if a bear trap at (x, y) overlaps with another bear trap or castle.

    Args:
        x: X coordinate.
        y: Y coordinate.
        bear_traps: List of bear trap dictionaries.
        castles: List of castle dictionaries.
        exclude_id: Bear trap ID to exclude from overlap check.

    Returns:
        Tuple of (has_overlap, overlapping_entity_id).
    """
    # Check against other bear traps
    for trap in bear_traps:
        if exclude_id and trap.get("id") == exclude_id:
            continue
        tx, ty = trap.get("x"), trap.get("y")
        if tx is None or ty is None:
            continue
        if x == tx and y == ty:
            return True, trap.get("id")

    # Check against castles (2x2)
    for castle in castles:
        cx, cy = castle.get("x"), castle.get("y")
        if cx is None or cy is None:
            continue
        # Check if point (x, y) is within the 2x2 castle area
        if cx <= x < cx + 2 and cy <= y < cy + 2:
            return True, castle.get("id")

    return False, None


=======
>>>>>>> copilot/add-bulk-edit-castles-ui
# ============================================================
# Routes
# ============================================================

# ============================================================
# Routes
# ============================================================


@app.get("/", response_class=HTMLResponse)
def index():
<<<<<<< HEAD
    """Serve the main HTML page.

    Returns:
        HTML page from static/index.html.
    """
=======
    """Serve the main HTML page."""
>>>>>>> copilot/add-bulk-edit-castles-ui
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))


@app.get("/api/map")
def get_map():
<<<<<<< HEAD
    """Get the current map configuration.

    Returns:
        Dictionary containing grid size, efficiency scale, and all entities
        (banners, bear traps, castles).
    """
    config = load_config()
    return {
        "grid_size": config["grid_size"],
        "efficiency_scale": config["efficiency_scale"],
=======
    """Get map configuration and entities."""
    config = load_config()
    return {
        "grid_size": config["grid_size"],
        # visual + logic config
        "efficiency_scale": config["efficiency_scale"],
        # entities (authoritative)
>>>>>>> copilot/add-bulk-edit-castles-ui
        "banners": config.get("banners", []),
        "bear_traps": config.get("bear_traps", []),
        "castles": config.get("castles", []),
    }


@app.get("/api/version")
def get_version():
<<<<<<< HEAD
    """Get the application version.

    Returns:
        Dictionary with version string.
    """
=======
    """Get application version."""
>>>>>>> copilot/add-bulk-edit-castles-ui
    try:
        with open(VERSION_PATH, "r", encoding="utf-8") as f:
            version_data = json.load(f)
        return version_data
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return {"version": DEFAULT_VERSION}


# ============================================================
<<<<<<< HEAD
# Castle validation constants and helpers
=======
# Castle Management
>>>>>>> copilot/add-bulk-edit-castles-ui
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
    """Sanitize and validate player name.

    Args:
        value: Player name string.

    Returns:
        Sanitized player name.

    Raises:
        HTTPException: If name exceeds maximum length.
    """
    value = value.strip()
    if not value:
        return ""
    if len(value) > MAX_PLAYER_NAME_LEN:
        raise HTTPException(400, "Player name too long")
    return value


def sanitise_int(value: Any, *, allow_none=False) -> int | None:
    """Sanitize and validate integer values.

    Args:
        value: Value to convert to integer.
        allow_none: Whether None is an acceptable value.

    Returns:
        Integer value or None if allowed.

    Raises:
        HTTPException: If value cannot be converted to integer.
    """
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
<<<<<<< HEAD
    """Update castle properties.

    Updates one or more properties of an existing castle. Validates all fields
    and broadcasts the update to connected clients via SSE.
=======
    """Update a single castle's fields.
>>>>>>> copilot/add-bulk-edit-castles-ui

    Args:
        payload: Dictionary containing castle id and fields to update.

    Returns:
        Dictionary with status and castle id.

    Raises:
<<<<<<< HEAD
        HTTPException: If castle not found or invalid fields provided.
=======
        HTTPException: If castle not found or validation fails.
>>>>>>> copilot/add-bulk-edit-castles-ui
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
    await notify_config_updated()

    return {
        "status": "ok",
        "id": castle_id,
    }


<<<<<<< HEAD
@app.post("/api/intent/move_castle")
async def move_castle(data: Dict[str, Any] = Body(...)):
    """Move a castle to a new position.

    Validates the move (bounds checking, overlap detection), updates the castle
    position, broadcasts the change via SSE, and unmarks the castle as busy.

    Args:
        data: Dictionary with 'id' (castle ID), 'x', and 'y' coordinates.

    Returns:
        Dictionary with success status.

    Raises:
        HTTPException: If validation fails or castle not found.
    """
    entity_id = data.get("id")
    x = data.get("x")
    y = data.get("y")

    if not entity_id or x is None or y is None:
        raise HTTPException(400, "Missing required fields: id, x, y")

    try:
        x = int(x)
        y = int(y)
    except (TypeError, ValueError):
        raise HTTPException(400, "Invalid coordinates")

    config = load_config()
    castles = config.get("castles", [])
    grid_size = config.get("grid_size", 28)

    castle = next((c for c in castles if c.get("id") == entity_id), None)
    if not castle:
        raise HTTPException(404, f"Castle '{entity_id}' not found")

    # Check if castle is locked
    if castle.get("locked", False):
        raise HTTPException(403, "Castle is locked")

    # Validate bounds (2x2 castle)
    if not is_within_bounds(x, y, grid_size, width=2, height=2):
        raise HTTPException(400, "Position out of bounds")

    # Check for overlaps with other castles
    has_overlap, overlapping_id = check_castle_overlap(
        x, y, castles, exclude_id=entity_id
    )
    if has_overlap:
        raise HTTPException(409, f"Position overlaps with castle '{overlapping_id}'")

    # Update position
    castle["x"] = x
    castle["y"] = y

    save_config(config)

    # Unmark as busy
    busy_set.discard(entity_id)

    await notify_config_updated()

=======
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
>>>>>>> copilot/add-bulk-edit-castles-ui
    return {"success": True}


@app.post("/api/intent/move_banner")
<<<<<<< HEAD
async def move_banner(data: Dict[str, Any] = Body(...)):
    """Move a banner to a new position.

    Validates the move (bounds checking), updates the banner position,
    broadcasts the change via SSE, and unmarks the banner as busy.

    Args:
        data: Dictionary with 'id' (banner ID), 'x', and 'y' coordinates.

    Returns:
        Dictionary with success status.

    Raises:
        HTTPException: If validation fails or banner not found.
    """
    entity_id = data.get("id")
    x = data.get("x")
    y = data.get("y")

    if not entity_id or x is None or y is None:
        raise HTTPException(400, "Missing required fields: id, x, y")

    try:
        x = int(x)
        y = int(y)
    except (TypeError, ValueError):
        raise HTTPException(400, "Invalid coordinates")

    config = load_config()
    banners = config.get("banners", [])
    grid_size = config.get("grid_size", 28)

    banner = next((b for b in banners if b.get("id") == entity_id), None)
    if not banner:
        raise HTTPException(404, f"Banner '{entity_id}' not found")

    # Check if banner is locked
    if banner.get("locked", False):
        raise HTTPException(403, "Banner is locked")

    # Validate bounds (1x1 banner)
    if not is_within_bounds(x, y, grid_size, width=1, height=1):
        raise HTTPException(400, "Position out of bounds")

    # Update position
    banner["x"] = x
    banner["y"] = y

    save_config(config)

    # Unmark as busy
    busy_set.discard(entity_id)

    await notify_config_updated()

=======
async def move_banner(data: Dict[str, Any]):
    """Handle banner move intent."""
    entity_id = data.get("id")
    x = data.get("x")
    y = data.get("y")
    # Placeholder: print the information sent
    print(f"Received move_banner intent: id={entity_id}, x={x}, y={y}")
    # TODO: Implement banner move validation and placement
>>>>>>> copilot/add-bulk-edit-castles-ui
    return {"success": True}


@app.post("/api/intent/move_bear_trap")
<<<<<<< HEAD
async def move_bear_trap(data: Dict[str, Any] = Body(...)):
    """Move a bear trap to a new position.

    Validates the move (bounds checking, overlap detection with castles and other traps),
    updates the bear trap position, broadcasts the change via SSE, and unmarks as busy.

    Args:
        data: Dictionary with 'id' (bear trap ID), 'x', and 'y' coordinates.

    Returns:
        Dictionary with success status.

    Raises:
        HTTPException: If validation fails or bear trap not found.
    """
    entity_id = data.get("id")
    x = data.get("x")
    y = data.get("y")

    if not entity_id or x is None or y is None:
        raise HTTPException(400, "Missing required fields: id, x, y")

    try:
        x = int(x)
        y = int(y)
    except (TypeError, ValueError):
        raise HTTPException(400, "Invalid coordinates")

    config = load_config()
    bear_traps = config.get("bear_traps", [])
    castles = config.get("castles", [])
    grid_size = config.get("grid_size", 28)

    bear_trap = next((t for t in bear_traps if t.get("id") == entity_id), None)
    if not bear_trap:
        raise HTTPException(404, f"Bear trap '{entity_id}' not found")

    # Check if bear trap is locked
    if bear_trap.get("locked", False):
        raise HTTPException(403, "Bear trap is locked")

    # Validate bounds (1x1 bear trap)
    if not is_within_bounds(x, y, grid_size, width=1, height=1):
        raise HTTPException(400, "Position out of bounds")

    # Check for overlaps
    has_overlap, overlapping_id = check_bear_trap_overlap(
        x, y, bear_traps, castles, exclude_id=entity_id
    )
    if has_overlap:
        raise HTTPException(409, f"Position overlaps with entity '{overlapping_id}'")

    # Update position
    bear_trap["x"] = x
    bear_trap["y"] = y

    save_config(config)

    # Unmark as busy
    busy_set.discard(entity_id)

    await notify_config_updated()

    return {"success": True}


@app.post("/api/intent/toggle_lock_castle")
async def toggle_lock_castle(data: Dict[str, Any] = Body(...)):
    """Toggle the locked state of a castle.

    Args:
        data: Dictionary with 'id' (castle ID).

    Returns:
        Dictionary with success status and new locked state.

    Raises:
        HTTPException: If castle not found.
    """
    entity_id = data.get("id")
    if not entity_id:
        raise HTTPException(400, "Missing castle id")

    config = load_config()
    castles = config.get("castles", [])

    castle = next((c for c in castles if c.get("id") == entity_id), None)
    if not castle:
        raise HTTPException(404, f"Castle '{entity_id}' not found")

    castle["locked"] = not castle.get("locked", False)
    save_config(config)
    await notify_config_updated()

    return {"success": True, "locked": castle["locked"]}


@app.post("/api/intent/toggle_lock_banner")
async def toggle_lock_banner(data: Dict[str, Any] = Body(...)):
    """Toggle the locked state of a banner.

    Args:
        data: Dictionary with 'id' (banner ID).

    Returns:
        Dictionary with success status and new locked state.

    Raises:
        HTTPException: If banner not found.
    """
    entity_id = data.get("id")
    if not entity_id:
        raise HTTPException(400, "Missing banner id")

    config = load_config()
    banners = config.get("banners", [])

    banner = next((b for b in banners if b.get("id") == entity_id), None)
    if not banner:
        raise HTTPException(404, f"Banner '{entity_id}' not found")

    banner["locked"] = not banner.get("locked", False)
    save_config(config)
    await notify_config_updated()

    return {"success": True, "locked": banner["locked"]}


@app.post("/api/intent/toggle_lock_bear_trap")
async def toggle_lock_bear_trap(data: Dict[str, Any] = Body(...)):
    """Toggle the locked state of a bear trap.

    Args:
        data: Dictionary with 'id' (bear trap ID).

    Returns:
        Dictionary with success status and new locked state.

    Raises:
        HTTPException: If bear trap not found.
    """
    entity_id = data.get("id")
    if not entity_id:
        raise HTTPException(400, "Missing bear trap id")

    config = load_config()
    bear_traps = config.get("bear_traps", [])

    bear_trap = next((t for t in bear_traps if t.get("id") == entity_id), None)
    if not bear_trap:
        raise HTTPException(404, f"Bear trap '{entity_id}' not found")

    bear_trap["locked"] = not bear_trap.get("locked", False)
    save_config(config)
    await notify_config_updated()

    return {"success": True, "locked": bear_trap["locked"]}


@app.post("/api/intent/lock_all_placed")
async def lock_all_placed():
    """Lock all castles that have been placed on the grid.

    Only locks castles that have valid x and y coordinates (i.e., are placed).
    Unplaced castles (x=None or y=None) are not affected.

    Returns:
        Dictionary with success status and count of locked castles.
    """
    config = load_config()
    castles = config.get("castles", [])

    locked_count = 0
    for castle in castles:
        # Only lock castles that are placed on the grid
        if castle.get("x") is not None and castle.get("y") is not None:
            if not castle.get("locked", False):
                castle["locked"] = True
                locked_count += 1

    save_config(config)
    await notify_config_updated()

    return {"success": True, "locked_count": locked_count}


@app.post("/api/intent/unlock_all")
async def unlock_all():
    """Unlock all castles, banners, and bear traps.

    Sets the locked state to False for all entities across the map.

    Returns:
        Dictionary with success status and counts of unlocked entities.
    """
    config = load_config()
    castles = config.get("castles", [])
    banners = config.get("banners", [])
    bear_traps = config.get("bear_traps", [])

    unlocked_castles = 0
    unlocked_banners = 0
    unlocked_bear_traps = 0

    for castle in castles:
        if castle.get("locked", False):
            castle["locked"] = False
            unlocked_castles += 1

    for banner in banners:
        if banner.get("locked", False):
            banner["locked"] = False
            unlocked_banners += 1

    for bear_trap in bear_traps:
        if bear_trap.get("locked", False):
            bear_trap["locked"] = False
            unlocked_bear_traps += 1

    save_config(config)
    await notify_config_updated()

    return {
        "success": True,
        "unlocked_castles": unlocked_castles,
        "unlocked_banners": unlocked_banners,
        "unlocked_bear_traps": unlocked_bear_traps,
    }


@app.post("/api/intent/move_castle_away")
async def move_castle_away(data: Dict[str, Any] = Body(...)):
    """Move a castle to an edge position (off the main grid).

    Moves the castle to position (0, 0) as a staging area.

    Args:
        data: Dictionary with 'id' (castle ID).

    Returns:
        Dictionary with success status.

    Raises:
        HTTPException: If castle not found.
    """
    entity_id = data.get("id")
    if not entity_id:
        raise HTTPException(400, "Missing castle id")

    config = load_config()
    castles = config.get("castles", [])

    castle = next((c for c in castles if c.get("id") == entity_id), None)
    if not castle:
        raise HTTPException(404, f"Castle '{entity_id}' not found")

    if castle.get("locked", False):
        raise HTTPException(403, "Castle is locked")

    # Move to edge/staging area
    castle["x"] = 0
    castle["y"] = 0

    save_config(config)

    # Unmark as busy
    busy_set.discard(entity_id)

    await notify_config_updated()

    return {"success": True}

=======
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
>>>>>>> copilot/add-bulk-edit-castles-ui


@app.post("/api/auto_place_castles")
async def auto_place_castles():
<<<<<<< HEAD
    """Auto-place castles on the grid using a simple algorithm.

    This is a placeholder implementation that arranges castles in a grid pattern.
    A more sophisticated algorithm could optimize based on efficiency, bear trap
    proximity, etc.

    Returns:
        Dictionary with success status and number of castles placed.
    """
    config = load_config()
    castles = config.get("castles", [])
    grid_size = config.get("grid_size", 28)

    # Simple grid placement: arrange castles in rows with spacing
    placed_count = 0
    row_spacing = 3
    col_spacing = 3
    x, y = 1, 1

    for castle in castles:
        if castle.get("locked", False):
            continue

        # Find next available position
        while True:
            has_overlap, _ = check_castle_overlap(
                x, y, castles, exclude_id=castle.get("id")
            )
            if not has_overlap and is_within_bounds(x, y, grid_size, width=2, height=2):
                castle["x"] = x
                castle["y"] = y
                placed_count += 1
                break

            # Move to next position
            x += col_spacing
            if x + 2 > grid_size:
                x = 1
                y += row_spacing
                if y + 2 > grid_size:
                    # No more space
                    break

            if y + 2 > grid_size:
                break

    save_config(config)
    await notify_config_updated()

    return {"success": True, "placed": placed_count}

=======
    """Auto-place castles (placeholder)."""
    print("Received auto_place_castles request")
    # TODO: Auto-place castles server-side
    return {"success": True}
>>>>>>> copilot/add-bulk-edit-castles-ui


@app.post("/api/upload_csv")
async def upload_csv(csv_file: UploadFile = File(...)):
<<<<<<< HEAD
    """Upload and parse a CSV file to update castle data.

    The CSV should contain castle information with columns matching the castle fields.
    This is a placeholder that acknowledges the upload but doesn't process it yet.

    Args:
        csv_file: Uploaded CSV file.

    Returns:
        Dictionary with success status and filename.
    """
    # Placeholder: In a full implementation, we would:
    # 1. Read and parse the CSV content
    # 2. Validate the data
    # 3. Merge with existing castles (match by player name or ID)
    # 4. Recompute priorities and efficiency
    # 5. Save config and broadcast update

    return {
        "success": True,
        "filename": csv_file.filename,
        "message": "CSV upload received",
    }


@app.post("/api/download_map_image")
async def download_map_image():
    """Generate and download a map image.

    This is a placeholder that would generate a server-side image of the current
    map layout. Full implementation would require image generation libraries.

    Returns:
        Dictionary with error message (not implemented).
    """
    # Placeholder: Full implementation would use PIL/Pillow or similar to:
    # 1. Create a blank image with grid
    # 2. Draw castles, bear traps, and banners
    # 3. Add labels and efficiency indicators
    # 4. Return as FileResponse with image/png content type

    return {
        "error": "Not implemented",
        "message": "Server-side image generation pending",
    }


@app.post("/api/intent/mark_busy")
async def mark_busy(data: Dict[str, Any] = Body(...)):
    """Mark an entity as busy.

    Used to indicate that a user is currently interacting with an entity,
    preventing concurrent modifications by other users.

    Args:
        data: Dictionary with 'id' (entity ID).

    Returns:
        Dictionary with success status.

    Raises:
        HTTPException: If id is missing.
    """
=======
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
>>>>>>> copilot/add-bulk-edit-castles-ui
    entity_id = data.get("id")
    if not entity_id:
        raise HTTPException(400, "Missing id")
    busy_set.add(entity_id)
    await broadcast_config(load_config())
    return {"success": True}


@app.post("/api/intent/unmark_busy")
<<<<<<< HEAD
async def unmark_busy(data: Dict[str, Any] = Body(...)):
    """Unmark an entity as busy.

    Removes the busy flag from an entity, allowing other users to interact with it.

    Args:
        data: Dictionary with 'id' (entity ID).

    Returns:
        Dictionary with success status.

    Raises:
        HTTPException: If id is missing.
    """
=======
async def unmark_busy(data: Dict[str, Any]):
    """Unmark entity as busy."""
>>>>>>> copilot/add-bulk-edit-castles-ui
    entity_id = data.get("id")
    if not entity_id:
        raise HTTPException(400, "Missing id")
    busy_set.discard(entity_id)
    await broadcast_config(load_config())
    return {"success": True}


@app.post("/api/castles/add")
async def add_castle():
<<<<<<< HEAD
    """Add a new castle to the map.

    Creates a new castle with default values and a unique ID. The castle is
    initially unplaced (x and y are None).

    Returns:
        Dictionary with success status and new castle ID.
    """
    config = load_config()
    castles = config.get("castles", [])

    # Generate new ID - extract numeric part from existing castle IDs
    existing_ids = []
    for c in castles:
        castle_id = c.get("id", "")
        if isinstance(castle_id, str) and castle_id.startswith("Castle "):
            try:
                existing_ids.append(int(castle_id.split(" ")[1]))
            except (ValueError, IndexError):
                pass
        elif isinstance(castle_id, int):
            existing_ids.append(castle_id)

    new_num = max(existing_ids, default=0) + 1
    new_id = f"Castle {new_num}"

    config["castles"].append(
        {
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
        }
    )
=======
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
>>>>>>> copilot/add-bulk-edit-castles-ui
    save_config(config)
    await notify_config_updated()
    return {"success": True, "id": new_id}


@app.post("/api/bear_traps/add")
async def add_bear_trap():
<<<<<<< HEAD
    """Add a new bear trap to the map.

    Creates a new bear trap with a unique ID. The trap is initially unplaced
    (x and y are None).

    Returns:
        Dictionary with success status and new bear trap ID.
    """
    config = load_config()
    bear_traps = config.get("bear_traps", [])

    # Generate new ID based on existing bear traps
    new_id = f"Bear {len(bear_traps) + 1}"

    config["bear_traps"].append({"id": new_id, "locked": False, "x": None, "y": None})
=======
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
>>>>>>> copilot/add-bulk-edit-castles-ui
    save_config(config)
    await notify_config_updated()
    return {"success": True, "id": new_id}


@app.post("/api/castles/delete")
<<<<<<< HEAD
async def delete_castle(data: Dict[str, Any] = Body(...)):
    """Delete a castle from the map.

    Removes the specified castle and broadcasts the update. Optionally logs
    a reason for deletion.

    Args:
        data: Dictionary with 'id' (castle ID) and optional 'reason'.

    Returns:
        Dictionary with success status.

    Raises:
        HTTPException: If castle ID is missing.
    """
    castle_id = data.get("id")
    if not castle_id:
        raise HTTPException(400, "Missing castle id")

    config = load_config()
    config["castles"] = [c for c in config["castles"] if c.get("id") != castle_id]
=======
async def delete_castle(data: Dict[str, Any]):
    """Delete a castle."""
    config = load_config()
    castle_id = data.get("id")
    config["castles"] = [
        c for c in config["castles"] if c.get("id") != castle_id
    ]
>>>>>>> copilot/add-bulk-edit-castles-ui
    save_config(config)

    # Unmark as busy if it was
    busy_set.discard(castle_id)

    reason = data.get("reason", "No reason provided")
    print(f"Deleted castle {castle_id} - Reason: {reason}")

    await notify_config_updated()
    return {"success": True}


# ============================================================
# GitHub Webhook Handler
# ============================================================

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
UPDATE_SCRIPT_PATH = os.path.join(BASE_DIR, "scripts", "update_and_restart.sh")


<<<<<<< HEAD
def verify_webhook_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verify the GitHub webhook signature using HMAC-SHA256.

    Args:
        payload_body: Raw request body bytes.
        signature_header: X-Hub-Signature-256 header value.

    Returns:
        True if signature is valid, False otherwise.
    """
=======
def verify_webhook_signature(payload_body: bytes,
                             signature_header: str) -> bool:
    """Verify the GitHub webhook signature using HMAC-SHA256."""
>>>>>>> copilot/add-bulk-edit-castles-ui
    if not WEBHOOK_SECRET:
        return False

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    hash_object = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"), msg=payload_body, digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()

    return hmac.compare_digest(expected_signature, signature_header)


async def trigger_update():
    """Trigger the update script in the background.

    Validates the script exists and is executable before running it in a
    detached process.
    """
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
            start_new_session=True,
        )
        print(f"Update script triggered: {UPDATE_SCRIPT_PATH}")
    except Exception as e:
        print(f"Error triggering update script: {e}")


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
):
<<<<<<< HEAD
    """Handle GitHub webhook events.

    Validates the payload signature using HMAC-SHA256 and triggers deployment
    updates when code is pushed to the main branch.

    Args:
        request: FastAPI request object.
        x_hub_signature_256: GitHub webhook signature header.
        x_github_event: GitHub event type header.

    Returns:
        Dictionary with status and message.

    Raises:
        HTTPException: If signature is invalid or payload cannot be parsed.
    """
=======
    """Handle GitHub webhook events and trigger updates on push to main."""
>>>>>>> copilot/add-bulk-edit-castles-ui
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
<<<<<<< HEAD
            return {"status": "success", "message": "Update triggered for main branch"}
=======
            return {
                "status": "success",
                "message": "Update triggered for main branch"
            }
>>>>>>> copilot/add-bulk-edit-castles-ui

    # For other events, just acknowledge receipt
    msg = f"Event {x_github_event} received but not processed"
    return {
        "status": "ok",
<<<<<<< HEAD
        "message": f"Event {x_github_event} received but not processed",
=======
        "message": msg
>>>>>>> copilot/add-bulk-edit-castles-ui
    }


# ============================================================
# Static files
# ============================================================

app.mount("/static", StaticFiles(directory="static"), name="static")
