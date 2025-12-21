"""
Validation and sanitization utilities.

This module contains functions for validating entity positions, checking overlaps,
and sanitizing user input data.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
"""

from typing import Any, List, Dict, Tuple, Optional

from fastapi import HTTPException

ALLOWED_CASTLE_FIELDS = {
    "player": str,
    "power": int,
    "player_level": int,
    "command_centre_level": int,
    "attendance": (int, type(None)),
    "rallies_30min": int,
    "preference": str,
}

VALID_PREFERENCES = {"BT1", "BT2", "BT1/2", "BT2/1"}
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


def sanitise_int(value: Any, *, allow_none: bool = False) -> Optional[int]:
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


def rectangles_overlap(x1, y1, w1, h1, x2, y2, w2, h2):
    """Check if two rectangles overlap.

    Args:
        x1, y1: Top-left of first rectangle
        w1, h1: Width and height of first rectangle
        x2, y2: Top-left of second rectangle
        w2, h2: Width and height of second rectangle

    Returns:
        True if they overlap, False otherwise
    """
    return not (x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1)


def check_castle_overlap(
        x: int, y: int, castles: List[Dict], exclude_id: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
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


def check_banner_overlap(
        x: int, y: int, banners: List[Dict], exclude_id: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """Check if a banner at (x, y) overlaps with another banner.

    Note: Banners can be placed anywhere, but this function checks for banner-banner overlaps
    if needed for other logic.

    Args:
        x: X coordinate.
        y: Y coordinate.
        banners: List of banner dictionaries.
        exclude_id: Banner ID to exclude from overlap check.

    Returns:
        Tuple of (has_overlap, overlapping_banner_id).
    """
    for banner in banners:
        if exclude_id and banner.get("id") == exclude_id:
            continue
        bx, by = banner.get("x"), banner.get("y")
        if bx is None or by is None:
            continue
        if x == bx and y == by:
            return True, banner.get("id", f"Banner@{bx},{by}")
    return False, None


def check_bear_trap_overlap(
        x: int, y: int, bear_traps: List[Dict], banners: List[Dict], exclude_id: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """Check if a 3x3 bear trap at (x, y) overlaps with other bear traps or banners.

    Bears can overlap castles but not banners or other bears.

    Args:
        x: X coordinate of bear trap (center).
        y: Y coordinate of bear trap (center).
        bear_traps: List of bear trap dictionaries.
        banners: List of banner dictionaries.
        exclude_id: Bear trap ID to exclude from overlap check.

    Returns:
        Tuple of (has_overlap, overlapping_entity_id).
    """
    # Bear occupies 3x3 from (x-1, y-1) to (x+1, y+1)
    bear_x1, bear_y1 = x - 1, y - 1

    for bear in bear_traps:
        if exclude_id and bear.get("id") == exclude_id:
            continue
        bx, by = bear.get("x"), bear.get("y")
        if bx is not None and by is not None:
            # Other bear occupies 3x3 from (bx-1, by-1) to (bx+1, by+1)
            if rectangles_overlap(bear_x1, bear_y1, 3, 3, bx - 1, by - 1, 3, 3):
                return True, bear.get("id", f"Bear@{bx},{by}")

    for banner in banners:
        bx, by = banner.get("x"), banner.get("y")
        if bx is not None and by is not None:
            # Banner is 1x1 at (bx, by)
            if rectangles_overlap(bear_x1, bear_y1, 3, 3, bx, by, 1, 1):
                return True, banner.get("id", f"Banner@{bx},{by}")

    return False, None


def check_castle_overlap_with_entities(
        x: int, y: int, bear_traps: List[Dict], banners: List[Dict]
) -> Tuple[bool, Optional[str]]:
    """Check if a 2x2 castle at (x, y) overlaps with any bear traps or banners.

    Castles cannot overlap with bears or banners.

    Args:
        x: X coordinate of castle (top-left).
        y: Y coordinate of castle (top-left).
        bear_traps: List of bear trap dictionaries.
        banners: List of banner dictionaries.

    Returns:
        Tuple of (has_overlap, overlapping_entity_id).
    """
    for bear in bear_traps:
        bx, by = bear.get("x"), bear.get("y")
        if bx is not None and by is not None:
            # Bear occupies 3x3 from (bx-1, by-1) to (bx+1, by+1)
            if rectangles_overlap(x, y, 2, 2, bx - 1, by - 1, 3, 3):
                return True, bear.get("id", f"Bear@{bx},{by}")

    for banner in banners:
        bx, by = banner.get("x"), banner.get("y")
        if bx is not None and by is not None:
            # Banner is 1x1 at (bx, by)
            if rectangles_overlap(x, y, 2, 2, bx, by, 1, 1):
                return True, banner.get("id", f"Banner@{bx},{by}")

    return False, None


def check_bear_trap_overlap_with_entities(
        x: int, y: int, bear_traps: List[Dict], banners: List[Dict], exclude_id: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """Check if a 3x3 bear trap at (x, y) overlaps with any other bear traps or banners.

    Args:
        x: X coordinate of bear trap.
        y: Y coordinate of bear trap.
        bear_traps: List of bear trap dictionaries.
        banners: List of banner dictionaries.
        exclude_id: Bear trap ID to exclude from overlap check.

    Returns:
        Tuple of (has_overlap, overlapping_entity_id).
    """
    # Bear trap occupies 3x3 from (x-1, y-1) to (x+1, y+1)
    bear_trap_x1, bear_trap_y1 = x - 1, y - 1

    # Check against other bear traps
    for trap in bear_traps:
        if exclude_id and trap.get("id") == exclude_id:
            continue
        tx, ty = trap.get("x"), trap.get("y")
        if tx is None or ty is None:
            continue
        # Other bear trap occupies 3x3 from (tx-1, ty-1) to (tx+1, ty+1)
        if rectangles_overlap(bear_trap_x1, bear_trap_y1, 3, 3, tx - 1, ty - 1, 3, 3):
            return True, trap.get("id", f"Bear@{tx},{ty}")

    # Check against banners (1x1)
    for banner in banners:
        bx, by = banner.get("x"), banner.get("y")
        if bx is None or by is None:
            continue
        # Banner is 1x1 at (bx, by)
        if rectangles_overlap(bear_trap_x1, bear_trap_y1, 3, 3, bx, by, 1, 1):
            return True, banner.get("id", f"Banner@{bx},{by}")

    return False, None


def is_tile_legal(x: int, y: int, grid_size: int, banners: List[Dict], bear_traps: List[Dict], occupied: set) -> Tuple[
    bool, str]:
    """Check if a 2x2 castle tile at (x,y) is legal.

    Args:
        x, y: Top-left of 2x2 area.
        grid_size: Size of the grid.
        banners: List of banners.
        bear_traps: List of bear traps.
        occupied: Set of occupied (x,y) tiles.

    Returns:
        (is_legal, reason)
    """
    # Bounds check for 2x2
    if not (0 <= x <= grid_size - 2 and 0 <= y <= grid_size - 2):
        return False, "out of bounds"

    # Check overlap with banners (1x1)
    for b in banners:
        bx, by = b.get('x'), b.get('y')
        if bx is not None and by is not None:
            if x <= bx < x + 2 and y <= by < y + 2:
                return False, f"overlaps banner at ({bx},{by})"

    # Check overlap with bear influence (3x3 centered)
    for bear in bear_traps:
        bx, by = bear.get('x'), bear.get('y')
        if bx is not None and by is not None:
            bear_min_x, bear_max_x = bx - 1, bx + 1
            bear_min_y, bear_max_y = by - 1, by + 1
            if not (x + 1 < bear_min_x or x > bear_max_x or y + 1 < bear_min_y or y > bear_max_y):
                return False, f"in bear influence at ({bx},{by})"

    # Check overlap with occupied tiles
    for dx in range(2):
        for dy in range(2):
            if (x + dx, y + dy) in occupied:
                return False, "overlaps occupied tile"

    return True, ""
