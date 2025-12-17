"""
Castle placement algorithms.

This module contains logic for automatically placing castles on the grid,
optimizing for spacing and avoiding overlaps.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
"""

from typing import List, Dict, Tuple

from .config import load_config, save_config
from .validation import is_within_bounds, check_castle_overlap, check_castle_overlap_with_entities, rectangles_overlap


async def auto_place_castles() -> Dict[str, int]:
    """Auto-place castles on the grid using a simple algorithm.

    This implementation places castles in a grid pattern, pushing existing
    unlocked castles outward to make space, and avoiding positions that
    would overlap with bear traps or banners.

    Returns:
        Dictionary with success status and number of castles placed.
    """
    config = load_config()
    castles = config.get("castles", [])
    bear_traps = config.get("bear_traps", [])
    banners = config.get("banners", [])
    grid_size = config.get("grid_size", 28)

    placed_count = 0
    row_spacing = 3
    col_spacing = 3
    x, y = 1, 1

    for castle in castles:
        if castle.get("locked", False):
            continue

        # Find next available position
        while True:
            # Check bounds
            if not is_within_bounds(x, y, grid_size, width=2, height=2):
                break

            # Check overlap with bears/banners
            has_entity_overlap, _ = check_castle_overlap_with_entities(x, y, bear_traps, banners)
            if has_entity_overlap:
                # Skip this position
                pass
            else:
                # Try to place here, pushing other castles if needed
                push_success, _ = push_castles_outward(x, y, castles, grid_size, bear_traps, banners, exclude_id=castle.get("id"))
                if push_success:
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

    return {"success": True, "placed": placed_count}


def push_castles_outward(
    placed_castle_x: int,
    placed_castle_y: int,
    castles: List[Dict],
    grid_size: int,
    bear_traps: List[Dict],
    banners: List[Dict],
    exclude_id: str = None
) -> Tuple[bool, str]:
    """Push unlocked castles outward that would overlap with a newly placed castle.

    Args:
        placed_castle_x: X position of the newly placed castle.
        placed_castle_y: Y position of the newly placed castle.
        castles: List of all castles.
        grid_size: Size of the grid.
        bear_traps: List of bear traps.
        banners: List of banners.
        exclude_id: ID of the castle being placed (to exclude from overlap checks).

    Returns:
        Tuple of (success, error_message). If success is False, error_message explains why.
    """
    # Find castles that would overlap with the new castle position
    overlapping_castles = []
    for castle in castles:
        if exclude_id and castle.get("id") == exclude_id:
            continue
        cx, cy = castle.get("x"), castle.get("y")
        if cx is None or cy is None:
            continue
        # Check if 2x2 rectangles overlap
        if not (placed_castle_x + 2 <= cx or cx + 2 <= placed_castle_x or
                placed_castle_y + 2 <= cy or cy + 2 <= placed_castle_y):
            overlapping_castles.append(castle)

    # Check if any overlapping castles are locked
    locked_overlaps = [c for c in overlapping_castles if c.get("locked", False)]
    if locked_overlaps:
        return False, f"Cannot place castle: overlaps with locked castle '{locked_overlaps[0]['id']}'"

    # Push unlocked overlapping castles outward
    for castle in overlapping_castles:
        if castle.get("locked", False):
            continue  # Should not happen due to check above, but safety
        push_castle_outward(castle, placed_castle_x, placed_castle_y, castles, grid_size, bear_traps, banners)

    return True, ""


def push_castle_outward(
    castle: Dict,
    avoid_x: int,
    avoid_y: int,
    all_castles: List[Dict],
    grid_size: int,
    bear_traps: List[Dict],
    banners: List[Dict]
):
    """Push a single castle outward to avoid overlap with a position.

    Args:
        castle: The castle dictionary to move.
        avoid_x: X position to avoid (center of 2x2 area).
        avoid_y: Y position to avoid (center of 2x2 area).
        all_castles: List of all castles for overlap checking.
        grid_size: Size of the grid.
        bear_traps: List of bear traps.
        banners: List of banners.
    """
    cx, cy = castle["x"], castle["y"]

    # Determine direction to push: away from the avoid position
    dx = cx + 1 - avoid_x if cx + 1 > avoid_x else cx - 1 - avoid_x
    dy = cy + 1 - avoid_y if cy + 1 > avoid_y else cy - 1 - avoid_y

    # Normalize to primary direction
    if abs(dx) > abs(dy):
        dy = 0
    elif abs(dy) > abs(dx):
        dx = 0
    else:
        # Equal, prefer horizontal
        dy = 0

    # Try to move in that direction
    step = 2  # Move by 2 to clear the 2x2 area
    new_x = cx + (dx // abs(dx) * step if dx != 0 else 0)
    new_y = cy + (dy // abs(dy) * step if dy != 0 else 0)

    # Ensure within bounds
    new_x = max(0, min(new_x, grid_size - 2))
    new_y = max(0, min(new_y, grid_size - 2))

    # Check if new position is free (no castle overlap and no bear/banner overlap)
    has_castle_overlap, _ = check_castle_overlap(new_x, new_y, all_castles, exclude_id=castle["id"])
    has_entity_overlap, _ = check_castle_overlap_with_entities(new_x, new_y, bear_traps, banners)
    if not has_castle_overlap and not has_entity_overlap:
        castle["x"] = new_x
        castle["y"] = new_y
        return

    # If blocked, try other directions
    for attempt in [(2, 0), (-2, 0), (0, 2), (0, -2), (2, 2), (-2, -2), (2, -2), (-2, 2)]:
        test_x = cx + attempt[0]
        test_y = cy + attempt[1]
        if (0 <= test_x <= grid_size - 2 and 0 <= test_y <= grid_size - 2):
            has_castle_overlap, _ = check_castle_overlap(test_x, test_y, all_castles, exclude_id=castle["id"])
            has_entity_overlap, _ = check_castle_overlap_with_entities(test_x, test_y, bear_traps, banners)
            if not has_castle_overlap and not has_entity_overlap:
                castle["x"] = test_x
                castle["y"] = test_y
                break


def move_castle_to_edge(
    castle: Dict,
    all_castles: List[Dict],
    grid_size: int,
    bear_traps: List[Dict],
    banners: List[Dict]
) -> bool:
    """Move a castle to the nearest edge of the map, pushing other castles out of the way.

    Args:
        castle: The castle dictionary to move.
        all_castles: List of all castles.
        grid_size: Size of the grid.
        bear_traps: List of bear traps.
        banners: List of banners.

    Returns:
        True if successfully moved, False if blocked by locked castles.
    """
    cx, cy = castle.get("x", 0), castle.get("y", 0)

    # Determine nearest edge
    dist_left = cx
    dist_right = grid_size - 2 - cx
    dist_top = cy
    dist_bottom = grid_size - 2 - cy

    min_dist = min(dist_left, dist_right, dist_top, dist_bottom)

    if min_dist == dist_left:
        target_x, target_y = 0, cy
    elif min_dist == dist_right:
        target_x, target_y = grid_size - 2, cy
    elif min_dist == dist_top:
        target_x, target_y = cx, 0
    else:  # bottom
        target_x, target_y = cx, grid_size - 2

    # Check if target position is clear (no castle overlap and no bear/banner overlap)
    has_castle_overlap, overlapping_id = check_castle_overlap(target_x, target_y, all_castles, exclude_id=castle["id"])
    has_entity_overlap, _ = check_castle_overlap_with_entities(target_x, target_y, bear_traps, banners)
    if not has_castle_overlap and not has_entity_overlap:
        castle["x"] = target_x
        castle["y"] = target_y
        return True

    # If blocked, we need to push the blocking castle(s) further
    # For simplicity, move to a clear edge position by trying positions
    for edge_positions in [
        [(x, 0) for x in range(0, grid_size - 1, 2)],  # Top edge
        [(x, grid_size - 2) for x in range(0, grid_size - 1, 2)],  # Bottom edge
        [(0, y) for y in range(0, grid_size - 1, 2)],  # Left edge
        [(grid_size - 2, y) for y in range(0, grid_size - 1, 2)],  # Right edge
    ]:
        for pos_x, pos_y in edge_positions:
            has_castle_overlap, overlapping_id = check_castle_overlap(pos_x, pos_y, all_castles, exclude_id=castle["id"])
            has_entity_overlap, _ = check_castle_overlap_with_entities(pos_x, pos_y, bear_traps, banners)
            if not has_castle_overlap and not has_entity_overlap:
                # Check if any castle at this position is locked
                overlapping_castle = next((c for c in all_castles if c.get("id") == overlapping_id), None)
                if overlapping_castle and overlapping_castle.get("locked", False):
                    continue  # Skip locked castles
                castle["x"] = pos_x
                castle["y"] = pos_y
                return True

    return False  # No clear edge position found


def push_castles_away_from_bear(
    bear_x: int,
    bear_y: int,
    castles: List[Dict],
    grid_size: int,
    bear_traps: List[Dict],
    banners: List[Dict]
) -> Tuple[bool, str]:
    """Push unlocked castles outward that would overlap with a bear trap position.

    Args:
        bear_x: X position of the bear trap.
        bear_y: Y position of the bear trap.
        castles: List of all castles.
        grid_size: Size of the grid.
        bear_traps: List of bear traps.
        banners: List of banners.

    Returns:
        Tuple of (success, error_message). If success is False, error_message explains why.
    """
    # Find castles that would overlap with the bear position (3x3)
    overlapping_castles = []
    for castle in castles:
        cx, cy = castle.get("x"), castle.get("y")
        if cx is None or cy is None:
            continue
        # Check if 2x2 castle overlaps with 3x3 bear
        if rectangles_overlap(cx, cy, 2, 2, bear_x - 1, bear_y - 1, 3, 3):
            overlapping_castles.append(castle)

    # Check if any overlapping castles are locked
    locked_overlaps = [c for c in overlapping_castles if c.get("locked", False)]
    if locked_overlaps:
        return False, f"Cannot place bear trap: overlaps with locked castle '{locked_overlaps[0]['id']}'"

    # Temporarily add the new bear to prevent castles from moving to its position
    temp_bear_traps = bear_traps + [{"x": bear_x, "y": bear_y}]

    # Push unlocked overlapping castles outward
    for castle in overlapping_castles:
        if castle.get("locked", False):
            continue  # Should not happen due to check above, but safety
        push_castle_outward(castle, bear_x, bear_y, castles, grid_size, temp_bear_traps, banners)

    return True, ""


def is_castle_invalid(
    castle: Dict,
    all_castles: List[Dict],
    bear_traps: List[Dict],
    banners: List[Dict]
) -> bool:
    """Check if a castle is in an invalid position.

    A castle is invalid if it overlaps with other castles, bears, or banners.

    Args:
        castle: The castle to check.
        all_castles: List of all castles.
        bear_traps: List of bear traps.
        banners: List of banners.

    Returns:
        True if the castle is in an invalid position.
    """
    cx, cy = castle.get("x"), castle.get("y")
    if cx is None or cy is None:
        return False  # Unplaced castles are not invalid

    # Check overlap with other castles
    has_castle_overlap, _ = check_castle_overlap(cx, cy, all_castles, exclude_id=castle["id"])
    if has_castle_overlap:
        return True

    # Check overlap with bears or banners
    has_entity_overlap, _ = check_castle_overlap_with_entities(cx, cy, bear_traps, banners)
    if has_entity_overlap:
        return True

    return False


def resolve_map_collisions(
    placed_x: int,
    placed_y: int,
    castles: List[Dict],
    grid_size: int,
    bear_traps: List[Dict],
    banners: List[Dict]
):
    """Resolve all collisions on the map by iteratively pushing invalid castles outward.

    Args:
        placed_x: X position of the placed entity.
        placed_y: Y position of the placed entity.
        castles: List of all castles.
        grid_size: Size of the grid.
        bear_traps: List of bear traps.
        banners: List of banners.
    """
    max_iterations = 100  # Prevent infinite loops
    iterations = 0

    while iterations < max_iterations:
        invalid_castles = [c for c in castles if is_castle_invalid(c, castles, bear_traps, banners)]
        if not invalid_castles:
            break

        for castle in invalid_castles:
            push_castle_outward(castle, placed_x, placed_y, castles, grid_size, bear_traps, banners)

        iterations += 1

    if iterations >= max_iterations:
        # Log or handle if it didn't resolve
        pass
