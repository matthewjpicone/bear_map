"""
Intent handlers for entity operations.

This module contains endpoints for moving entities, toggling locks, managing
busy states, and other interactive operations on the map.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
"""

from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException

from logic.config import load_config, save_config
from logic.validation import is_within_bounds, check_bear_trap_overlap
from logic.placement import auto_place_castles
from server.broadcast import notify_config_updated, busy_set

router = APIRouter()


@router.post("/api/intent/move_castle")
async def move_castle(data: Dict[str, Any] = Body(...)):
    """Move a castle to a new position.

    Validates the move according to placement priorities:
    - Reverts if overlaps with bears or banners
    - Pushes unlocked castles outward if they would overlap
    - Fails if locked castles would be affected

    Args:
        data: Dictionary with 'id' (castle ID), 'x', and 'y' coordinates.

    Returns:
        Dictionary with success status or error message.

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
    bear_traps = config.get("bear_traps", [])
    banners = config.get("banners", [])
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

    # Check if new position overlaps with bears or banners (castles can't overlap these)
    from logic.validation import check_castle_overlap_with_entities
    has_overlap, overlapping_id = check_castle_overlap_with_entities(x, y, bear_traps, banners)
    if has_overlap:
        # Revert to original position and show error
        await notify_config_updated()  # Ensure frontend is in sync
        return {"success": False, "error": "Move failed: overlaps with bear trap or banner", "message": "Move failed: position overlaps with an existing bear trap or banner"}

    # Check for overlaps with other castles and push them if needed
    from logic.placement import push_castles_outward
    push_success, push_error = push_castles_outward(x, y, castles, grid_size, bear_traps, banners, exclude_id=entity_id)
    if not push_success:
        return {"success": False, "error": push_error}

    # Resolve any cascading collisions
    from logic.placement import resolve_map_collisions
    resolve_map_collisions(x, y, castles, grid_size, bear_traps, banners)

    # Update position
    castle["x"] = x
    castle["y"] = y

    # Update round trip time for this castle
    from logic.placement import update_castle_round_trip_time
    update_castle_round_trip_time(castle, bear_traps)

    # Recompute efficiency scores for all castles (this also calculates map scores)
    from logic.scoring import compute_efficiency
    castles = compute_efficiency(config, castles)


    save_config(config)

    # Unmark as busy
    busy_set.discard(entity_id)

    await notify_config_updated()

    return {"success": True}


@router.post("/api/intent/move_banner")
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

    return {"success": True}


@router.post("/api/intent/move_bear_trap")
async def move_bear_trap(data: Dict[str, Any] = Body(...)):
    """Move a bear trap to a new position.

    Bears can overlap castles but not banners or other bears.
    When placing, pushes unlocked castles out of the way.

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
    banners = config.get("banners", [])
    castles = config.get("castles", [])
    grid_size = config.get("grid_size", 28)

    bear_trap = next((t for t in bear_traps if t.get("id") == entity_id), None)
    if not bear_trap:
        raise HTTPException(404, f"Bear trap '{entity_id}' not found")

    # Check if bear trap is locked
    if bear_trap.get("locked", False):
        raise HTTPException(403, "Bear trap is locked")

    # Validate bounds (3x3 bear trap)
    if not is_within_bounds(x, y, grid_size, width=3, height=3):
        raise HTTPException(400, "Position out of bounds")

    # Check for overlaps (bears can overlap castles but not banners or other bears)
    has_overlap, overlapping_id = check_bear_trap_overlap(
        x, y, bear_traps, banners, exclude_id=entity_id
    )
    if has_overlap:
        raise HTTPException(409, f"Position overlaps with entity '{overlapping_id}'")

    # Check for castle overlaps and push them if needed
    from logic.placement import push_castles_away_from_bear
    push_success, push_error = push_castles_away_from_bear(x, y, castles, grid_size, bear_traps, banners)
    if not push_success:
        await notify_config_updated()  # Ensure frontend is in sync
        return {"success": False, "error": push_error, "message": "Can't place bear trap - it would overlap with a locked castle"}

    # Resolve any cascading collisions
    from logic.placement import resolve_map_collisions
    temp_bear_traps = bear_traps + [{"x": x, "y": y}]
    resolve_map_collisions(x, y, castles, grid_size, temp_bear_traps, banners)

    # Update position
    bear_trap["x"] = x
    bear_trap["y"] = y

    # Update round trip times for all castles (bear movement affects all)
    from logic.placement import update_all_round_trip_times
    update_all_round_trip_times(castles, bear_traps)

    # Recompute efficiency scores for all castles (this also calculates map scores)
    from logic.scoring import compute_efficiency
    castles = compute_efficiency(config, castles)


    save_config(config)

    # Unmark as busy
    busy_set.discard(entity_id)

    await notify_config_updated()

    return {"success": True}


@router.post("/api/intent/toggle_lock_castle")
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


@router.post("/api/intent/toggle_lock_banner")
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


@router.post("/api/intent/toggle_lock_bear_trap")
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


@router.post("/api/intent/lock_all_placed")
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


@router.post("/api/intent/unlock_all")
async def unlock_all():
    """Unlock all castles (does not affect banners or bear traps).

    Returns:
        Dictionary with success status and count of unlocked castles.
    """
    config = load_config()
    castles = config.get("castles", [])

    unlocked_castles = 0

    for castle in castles:
        if castle.get("locked", False):
            castle["locked"] = False
            unlocked_castles += 1

    save_config(config)
    await notify_config_updated()

    return {
        "success": True,
        "unlocked_castles": unlocked_castles,
    }


@router.post("/api/intent/move_castle_away")
async def move_castle_away(data: Dict[str, Any] = Body(...)):
    """Move a castle to the nearest edge of the map, pushing other castles out of the way.

    Args:
        data: Dictionary with 'id' (castle ID).

    Returns:
        Dictionary with success status.

    Raises:
        HTTPException: If castle not found or cannot be moved.
    """
    entity_id = data.get("id")
    if not entity_id:
        raise HTTPException(400, "Missing castle id")

    config = load_config()
    castles = config.get("castles", [])
    bear_traps = config.get("bear_traps", [])
    banners = config.get("banners", [])
    grid_size = config.get("grid_size", 28)

    castle = next((c for c in castles if c.get("id") == entity_id), None)
    if not castle:
        raise HTTPException(404, f"Castle '{entity_id}' not found")

    if castle.get("locked", False):
        raise HTTPException(403, "Castle is locked")

    # Move to nearest edge, pushing other castles
    from logic.placement import move_castle_to_edge
    success = move_castle_to_edge(castle, castles, grid_size, bear_traps, banners)
    if not success:
        raise HTTPException(409, "Cannot move castle: no available edge position")

    # Update round trip time for this castle
    from logic.placement import update_castle_round_trip_time
    update_castle_round_trip_time(castle, bear_traps)

    # Recompute efficiency scores for all castles (this also calculates map scores)
    from logic.scoring import compute_efficiency
    castles = compute_efficiency(config, castles)

    save_config(config)

    # Unmark as busy
    busy_set.discard(entity_id)

    await notify_config_updated()

    return {"success": True}


@router.post("/api/auto_place_castles")
async def auto_place_castles_endpoint():
    """Auto-place castles on the grid using a simple algorithm.

    This is a placeholder implementation that arranges castles in a grid pattern.
    A more sophisticated algorithm could optimize based on efficiency, bear trap
    proximity, etc.

    Returns:
        Dictionary with success status and number of castles placed.
    """
    result = await auto_place_castles()
    await notify_config_updated()
    return result


@router.post("/api/intent/mark_busy")
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
    entity_id = data.get("id")
    if not entity_id:
        raise HTTPException(400, "Missing id")
    busy_set.add(entity_id)
    await notify_config_updated()
    return {"success": True}


@router.post("/api/intent/unmark_busy")
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
    entity_id = data.get("id")
    if not entity_id:
        raise HTTPException(400, "Missing id")
    busy_set.discard(entity_id)
    await notify_config_updated()
    return {"success": True}


@router.post("/api/bear_traps/add")
async def add_bear_trap():
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

    save_config(config)
    await notify_config_updated()
    return {"success": True, "id": new_id}


@router.post("/api/download_map_image")
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


@router.post("/api/move_all_out_of_way")
async def move_all_out_of_way():
    """Move all unlocked castles to the edges of the map.

    Iterates through all unlocked castles and moves each one to the nearest
    available edge position, ensuring no overlaps.

    Returns:
        Dictionary with success status and count of moved castles.
    """
    config = load_config()
    castles = config.get("castles", [])
    bear_traps = config.get("bear_traps", [])
    banners = config.get("banners", [])
    grid_size = config.get("grid_size", 28)

    moved_count = 0

    for castle in castles:
        if not castle.get("locked", False) and castle.get("x") is not None and castle.get("y") is not None:
            # Move this castle to the edge
            from logic.placement import move_castle_to_edge
            success = move_castle_to_edge(castle, castles, grid_size, bear_traps, banners)
            if success:
                moved_count += 1

    if moved_count > 0:
        # Update round trip times for all castles (positions changed)
        from logic.placement import update_all_round_trip_times
        update_all_round_trip_times(castles, bear_traps)

        # Recompute efficiency scores (this also calculates map scores)
        from logic.scoring import compute_efficiency
        compute_efficiency(config, castles)

        save_config(config)
        await notify_config_updated()

    return {"success": True, "moved_count": moved_count}
