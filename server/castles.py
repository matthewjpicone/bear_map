"""
Castle management API routes.

This module contains endpoints for creating, updating, and deleting castles,
including bulk operations and data validation.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
"""

from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, UploadFile, File

from logic.config import load_config, save_config
from logic.validation import ALLOWED_CASTLE_FIELDS, VALID_PREFERENCES, sanitise_player_name, sanitise_int
from server.broadcast import notify_config_updated

router = APIRouter()


@router.post("/api/castles/update")
async def update_castle(payload: Dict[str, Any] = Body(...)):
    """Update castle properties.

    Updates one or more properties of an existing castle. Validates all fields
    and broadcasts the update to connected clients via SSE.

    Args:
        payload: Dictionary containing castle id and fields to update.

    Returns:
        Dictionary with status and castle id.

    Raises:
        HTTPException: If castle not found or invalid fields provided.
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


@router.post("/api/castles/bulk_update")
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
    if "preference" in updates and updates["preference"] not in VALID_PREFERENCES:
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


@router.post("/api/castles/add")
async def add_castle():
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

    save_config(config)
    await notify_config_updated()
    return {"success": True, "id": new_id}


@router.post("/api/castles/delete")
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

    save_config(config)

    # Unmark as busy if it was
    from server.broadcast import busy_set
    busy_set.discard(castle_id)

    reason = data.get("reason", "No reason provided")
    print(f"Deleted castle {castle_id} - Reason: {reason}")

    await notify_config_updated()
    return {"success": True}


@router.post("/api/upload_csv")
async def upload_csv(csv_file: UploadFile = File(...)):
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
