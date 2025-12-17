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


def check_bear_trap_overlap(
    x: int, y: int, bear_traps: List[Dict], castles: List[Dict], exclude_id: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
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
