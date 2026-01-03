"""
Castle management API routes.

This module contains endpoints for creating, updating, and deleting castles,
including bulk operations and data validation.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
"""

from typing import Any, Dict

from fastapi import APIRouter, Body, File, HTTPException, UploadFile

from logic.config import load_config, save_config
from logic.validation import (
    ALLOWED_CASTLE_FIELDS,
    VALID_PREFERENCES,
    sanitise_int,
    sanitise_player_name,
)
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
    data_fields_changed = False

    for key, value in payload.items():
        if key == "id":
            continue

        if key not in ALLOWED_CASTLE_FIELDS:
            raise HTTPException(400, f"Illegal field: {key}")

        if key == "player":
            castle["player"] = sanitise_player_name(str(value))
            data_fields_changed = True
        elif key == "discord_username":
            castle["discord_username"] = sanitise_player_name(str(value))
            data_fields_changed = True
        elif key == "preference":
            if value not in VALID_PREFERENCES:
                raise HTTPException(400, "Invalid preference")
            castle["preference"] = value
        elif key == "attendance":
            castle[key] = sanitise_int(value, allow_none=True)
        elif key in ["power", "player_level", "command_centre_level"]:
            castle[key] = sanitise_int(value)
            data_fields_changed = True
        else:
            castle[key] = sanitise_int(value)

        updated = True

    if not updated:
        raise HTTPException(400, "No valid fields supplied")

    # Update last_updated only if player data fields changed
    if data_fields_changed:
        from datetime import datetime

        castle["last_updated"] = datetime.now().isoformat()

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

        data_fields_changed = False

        # Apply updates to this castle
        for key, value in updates.items():
            if key == "player":
                castle["player"] = sanitise_player_name(str(value))
                data_fields_changed = True
            elif key == "discord_username":
                castle["discord_username"] = sanitise_player_name(str(value))
                data_fields_changed = True
            elif key == "preference":
                castle["preference"] = value
            elif key == "attendance":
                castle[key] = sanitise_int(value, allow_none=True)
            elif key == "locked":
                # Special handling for locked field (boolean)
                if not isinstance(value, bool):
                    raise HTTPException(400, "Invalid locked value")
                castle[key] = value
            elif key in ["power", "player_level", "command_centre_level"]:
                castle[key] = sanitise_int(value)
                data_fields_changed = True
            else:
                castle[key] = sanitise_int(value)

        # Update last_updated only if player data fields changed
        if data_fields_changed:
            from datetime import datetime

            castle["last_updated"] = datetime.now().isoformat()

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
async def add_castle(payload: Dict[str, Any] = Body(None)):
    """Add a new castle to the map.

    Creates a new castle with provided values. The castle is
    initially unplaced (x and y are None).

    Args:
        payload: Dictionary containing:
            - id: Required castle ID (player account ID)
            - player: Player name
            - discord_username: Discord username
            - power: Castle power
            - player_level: Player level
            - preference: Bear trap preference

    Returns:
        Dictionary with success status and new castle ID.

    Raises:
        HTTPException: If castle ID is not provided or already exists.
    """
    config = load_config()
    castles = config.get("castles", [])

    # Extract payload data if provided
    payload = payload or {}
    custom_id = payload.get("id", "").strip()
    player_name = payload.get("player", "").strip()
    discord_username = payload.get("discord_username", "").strip()
    power = payload.get("power", 0)
    player_level = payload.get("player_level", 0)
    preference = payload.get("preference", "BT1/2")

    # Castle ID is required
    if not custom_id:
        raise HTTPException(400, "Castle ID is required")

    # Check if custom ID already exists
    if any(c.get("id") == custom_id for c in castles):
        raise HTTPException(400, f"Castle ID '{custom_id}' already exists")

    # Validate preference is in allowed list
    if preference not in VALID_PREFERENCES:
        raise HTTPException(
            400,
            f"Invalid preference '{preference}'. "
            f"Must be one of: {', '.join(VALID_PREFERENCES)}"
        )

    new_id = custom_id

    new_castle = {
        "id": new_id,
        "player": player_name,
        "discord_username": discord_username,
        "power": power,
        "player_level": player_level,
        "command_centre_level": 0,
        "attendance": 0,
        "rallies_30min": 5,
        "preference": preference,
        "locked": False,
        "priority": None,
        "efficiency": None,
        "round_trip": "NA",
        "last_updated": None,
        "x": None,
        "y": None,
    }

    config["castles"].append(new_castle)
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
