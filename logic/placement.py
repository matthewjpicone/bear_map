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
from .scoring import compute_priority, compute_efficiency, get_walkable_tiles, chebyshev_distance, compute_ideal_allocation


async def auto_place_castles() -> Dict[str, int]:
    """Auto-place castles on the grid to minimize efficiency scores.

    Places castles in priority order, selecting positions that minimize
    individual efficiency scores based on travel time and blocking penalties.

    Returns:
        Dictionary with success status and number of castles placed.
    """
    config = load_config()
    castles = config.get("castles", [])
    bear_traps = config.get("bear_traps", [])
    banners = config.get("banners", [])
    grid_size = config.get("grid_size", 28)

    # Compute priority
    castles = compute_priority(castles)

    # Compute ideal allocation
    compute_ideal_allocation(config, castles)

    # Get walkable tiles
    walkable = get_walkable_tiles(grid_size, banners, bear_traps)

    # Occupied by locked entities
    occupied = set()
    for b in bear_traps:
        if b.get("locked") and b.get("x") is not None and b.get("y") is not None:
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    occupied.add((b["x"] + dx, b["y"] + dy))
    for ban in banners:
        if ban.get("locked") and ban.get("x") is not None and ban.get("y") is not None:
            occupied.add((ban["x"], ban["y"]))
    for c in castles:
        if c.get("locked") and c.get("x") is not None and c.get("y") is not None:
            for dx in range(2):
                for dy in range(2):
                    occupied.add((c["x"] + dx, c["y"] + dy))

    # Sort castles by priority (highest first)
    castles.sort(key=lambda c: c.get("priority_score", 0), reverse=True)

    K = 80  # candidates limit
    placed_count = 0

    for castle in castles:
        if castle.get("locked"):
            continue

        preference = castle.get("preference", "both").lower()
        candidates = []

        if preference == "bear 1":
            bear = next((b for b in bear_traps if b.get("id") == "Bear 1"), None)
            if bear and bear.get("x") is not None and bear.get("y") is not None:
                candidates = sorted(
                    [t for t in walkable if t not in occupied and 0 <= t[0] <= grid_size - 2 and 0 <= t[1] <= grid_size - 2],
                    key=lambda t: chebyshev_distance(t[0], t[1], bear["x"], bear["y"])
                )[:K]
        elif preference == "bear 2":
            bear = next((b for b in bear_traps if b.get("id") == "Bear 2"), None)
            if bear and bear.get("x") is not None and bear.get("y") is not None:
                candidates = sorted(
                    [t for t in walkable if t not in occupied and 0 <= t[0] <= grid_size - 2 and 0 <= t[1] <= grid_size - 2],
                    key=lambda t: chebyshev_distance(t[0], t[1], bear["x"], bear["y"])
                )[:K]
        else:  # both
            bear1 = next((b for b in bear_traps if b.get("id") == "Bear 1"), None)
            bear2 = next((b for b in bear_traps if b.get("id") == "Bear 2"), None)
            if bear1 and bear2 and bear1.get("x") is not None and bear1.get("y") is not None and bear2.get("x") is not None and bear2.get("y") is not None:
                mid = grid_size // 2
                spine_cols = [mid - 1, mid]
                spine_tiles = [t for t in walkable if t[0] in spine_cols and t not in occupied and 0 <= t[0] <= grid_size - 2 and 0 <= t[1] <= grid_size - 2]
                if spine_tiles:
                    candidates = sorted(
                        spine_tiles,
                        key=lambda t: min(
                            chebyshev_distance(t[0], t[1], bear1["x"], bear1["y"]),
                            chebyshev_distance(t[0], t[1], bear2["x"], bear2["y"])
                        )
                    )[:K]
                else:
                    # Fallback to best of bear1/bear2
                    candidates = sorted(
                        [t for t in walkable if t not in occupied and 0 <= t[0] <= grid_size - 2 and 0 <= t[1] <= grid_size - 2],
                        key=lambda t: min(
                            chebyshev_distance(t[0], t[1], bear1["x"], bear1["y"]),
                            chebyshev_distance(t[0], t[1], bear2["x"], bear2["y"])
                        )
                    )[:K]

        if not candidates:
            continue

        # Evaluate each candidate
        best_tile = None
        best_eff = float("inf")
        for tx, ty in candidates:
            # Temporarily set position
            orig_x = castle.get("x")
            orig_y = castle.get("y")
            castle["x"] = tx
            castle["y"] = ty
            eff = compute_efficiency_for_castle(castle, castles, bear_traps, grid_size)
            if eff < best_eff:
                best_eff = eff
                best_tile = (tx, ty)
            # Restore
            if orig_x is not None:
                castle["x"] = orig_x
            else:
                castle.pop("x", None)
            if orig_y is not None:
                castle["y"] = orig_y
            else:
                castle.pop("y", None)

        if best_tile:
            castle["x"] = best_tile[0]
            castle["y"] = best_tile[1]
            # Mark occupied
            for dx in range(2):
                for dy in range(2):
                    occupied.add((best_tile[0] + dx, best_tile[1] + dy))
            placed_count += 1

    # After placement, recompute full scores
    castles = compute_efficiency(config, castles)

    # Compute map score
    occupied_after = set()
    for b in bear_traps:
        if b.get("x") is not None and b.get("y") is not None:
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    occupied_after.add((b["x"] + dx, b["y"] + dy))
    for ban in banners:
        if ban.get("x") is not None and ban.get("y") is not None:
            occupied_after.add((ban["x"], ban["y"]))
    for c in castles:
        if c.get("x") is not None and c.get("y") is not None:
            for dx in range(2):
                for dy in range(2):
                    occupied_after.add((c["x"] + dx, c["y"] + dy))

    empty_tiles = [t for t in walkable if t not in occupied_after]
    empty_score_100 = 0
    if empty_tiles:
        bear1 = next((b for b in bear_traps if b.get("id") == "Bear 1"), None)
        bear2 = next((b for b in bear_traps if b.get("id") == "Bear 2"), None)
        if bear1 and bear2:
            distances = [
                min(chebyshev_distance(t[0], t[1], bear1["x"], bear1["y"]),
                    chebyshev_distance(t[0], t[1], bear2["x"], bear2["y"]))
                for t in empty_tiles
            ]
            T_max = grid_size * 2
            q_values = [1 - min(1, d / T_max) for d in distances]
            empty_score_100 = round(100 * (sum(q_values) / len(q_values)))

    placed_castles = [c for c in castles if c.get("x") is not None and c.get("y") is not None]
    avg_eff = sum(c.get("efficiency_score", 0) for c in placed_castles) / len(placed_castles) if placed_castles else 0

    scaled_eff_900 = 9 * avg_eff
    scaled_eff_900 *= 0.9
    map_eff_component = 900 - scaled_eff_900
    empty_component_900 = 9 * empty_score_100
    map_score_900 = round(0.85 * map_eff_component + 0.15 * empty_component_900)
    map_score_percent = round(100 * map_score_900 / 900, 1)

    # Persist
    config["map_score_900"] = map_score_900
    config["map_score_percent"] = map_score_percent
    config["empty_score_100"] = empty_score_100
    config["efficiency_avg"] = round(avg_eff, 1)

    # Update round trip times
    update_all_round_trip_times(castles, bear_traps)

    save_config(config)

    return {"success": True, "placed": placed_count}


def compute_efficiency_for_castle(castle: Dict, all_castles: List[Dict], bear_traps: List[Dict], grid_size: int) -> float:
    """Compute efficiency score for a single castle given current positions."""
    # Compute actual_travel_time for all
    for c in all_castles:
        if c.get("x") is not None and c.get("y") is not None:
            pref = c.get("preference", "both").lower()
            if pref == "bear 1":
                bear = next((b for b in bear_traps if b.get("id") == "Bear 1"), None)
                if bear and bear.get("x") is not None and bear.get("y") is not None:
                    c["actual_travel_time"] = chebyshev_distance(c["x"], c["y"], bear["x"], bear["y"])
            elif pref == "bear 2":
                bear = next((b for b in bear_traps if b.get("id") == "Bear 2"), None)
                if bear and bear.get("x") is not None and bear.get("y") is not None:
                    c["actual_travel_time"] = chebyshev_distance(c["x"], c["y"], bear["x"], bear["y"])
            else:
                bear1 = next((b for b in bear_traps if b.get("id") == "Bear 1"), None)
                bear2 = next((b for b in bear_traps if b.get("id") == "Bear 2"), None)
                if bear1 and bear2 and bear1.get("x") is not None and bear1.get("y") is not None and bear2.get("x") is not None and bear2.get("y") is not None:
                    c["actual_travel_time"] = min(
                        chebyshev_distance(c["x"], c["y"], bear1["x"], bear1["y"]),
                        chebyshev_distance(c["x"], c["y"], bear2["x"], bear2["y"])
                    )

    # Regret
    ideal = castle.get("ideal_travel_time", 0)
    actual = castle.get("actual_travel_time")
    if actual is None:
        return 100
    regret = max(0, actual - ideal)

    # Tscale
    all_regrets = [max(0, c.get("actual_travel_time", 0) - c.get("ideal_travel_time", 0)) for c in all_castles if c.get("actual_travel_time") is not None]
    nonzero = [r for r in all_regrets if r > 0]
    Tscale = sorted(nonzero)[int(0.9 * len(nonzero))] if nonzero else 1
    base = min(1, regret / Tscale) if Tscale > 0 else 0

    # Block penalty
    block = 0
    for other in all_castles:
        if other["id"] == castle["id"]:
            continue
        if other.get("priority_rank_100", 0) < castle.get("priority_rank_100", 0) and other.get("actual_travel_time", 0) > castle.get("actual_travel_time", 0):
            rank_diff = castle["priority_rank_100"] - other["priority_rank_100"]
            sigmoid = 1 / (1 + 2.718 ** (-(rank_diff - 10) / 5))
            block += (other["actual_travel_time"] - castle["actual_travel_time"]) * sigmoid

    block_p90 = sorted([block] + [0])[int(0.9 * 1)] if [block] else 0  # rough
    block_norm = block / max(block_p90, 1e-6)

    eff = 100 * min(1, 0.75 * base + 0.25 * block_norm)
    return round(eff)


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
        push_castle_outward(castle, placed_castle_x, placed_castle_y, castles, grid_size, bear_traps, banners, exclude_id)

    return True, ""


def push_castle_outward(
    castle: Dict,
    avoid_x: int,
    avoid_y: int,
    all_castles: List[Dict],
    grid_size: int,
    bear_traps: List[Dict],
    banners: List[Dict],
    exclude_id: str = None
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


# ==========================
# ROUND TRIP TIME CALCULATIONS
# ==========================

def calculate_euclidean_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate straight-line (as the crow flies) distance between two points.

    Args:
        x1, y1: Coordinates of first point
        x2, y2: Coordinates of second point

    Returns:
        Euclidean distance in tiles
    """
    return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5


def calculate_travel_time(distance: float) -> float:
    """Calculate travel time for a given distance.

    Based on: 15 tiles = 36 seconds straight line
    Rate: 36/15 = 2.4 seconds per tile

    Args:
        distance: Distance in tiles

    Returns:
        Travel time in seconds
    """
    travel_rate = 36 / 15  # seconds per tile
    return distance * travel_rate


def calculate_round_trip_time(castle: Dict, bear_traps: List[Dict]) -> float:
    """Calculate round trip time for a castle to its bear trap(s).

    Base time: 5 minutes (300 seconds) + travel to bear + travel from bear

    Args:
        castle: Castle dictionary
        bear_traps: List of all bear traps

    Returns:
        Round trip time in seconds, or None if no valid bear found
    """
    preference = castle.get("preference", "Both").lower()
    base_time = 300  # 5 minutes in seconds

    if preference == "both":
        # Calculate for both bears and average
        bear1 = next((b for b in bear_traps if b.get("id") == "Bear 1"), None)
        bear2 = next((b for b in bear_traps if b.get("id") == "Bear 2"), None)

        if not bear1 or not bear2:
            return None

        time1 = calculate_single_round_trip(castle, bear1)
        time2 = calculate_single_round_trip(castle, bear2)

        if time1 is None or time2 is None:
            return None

        return (time1 + time2) / 2

    else:
        # Calculate for specific bear
        bear = next((b for b in bear_traps if b.get("id", "").lower() == preference), None)
        if not bear:
            return None
        return calculate_single_round_trip(castle, bear)


def calculate_single_round_trip(castle: Dict, bear: Dict) -> float:
    """Calculate round trip time for a castle to a specific bear.

    Args:
        castle: Castle dictionary
        bear: Bear trap dictionary

    Returns:
        Round trip time in seconds, or None if positions invalid
    """
    castle_x = castle.get("x")
    castle_y = castle.get("y")
    bear_x = bear.get("x")
    bear_y = bear.get("y")

    if castle_x is None or castle_y is None or bear_x is None or bear_y is None:
        return None

    # Calculate distance (castle center to bear center)
    distance = calculate_euclidean_distance(castle_x + 1, castle_y + 1, bear_x + 1, bear_y + 1)

    # Travel time one way
    travel_time = calculate_travel_time(distance)

    # Round trip = base + to bear + from bear
    base_time = 300  # 5 minutes
    return base_time + 2 * travel_time


def update_all_round_trip_times(castles: List[Dict], bear_traps: List[Dict]):
    """Update round trip times for all castles.

    Args:
        castles: List of castle dictionaries
        bear_traps: List of bear trap dictionaries
    """
    for castle in castles:
        round_trip = calculate_round_trip_time(castle, bear_traps)
        if round_trip is not None:
            castle["round_trip"] = round(round_trip)  # Round to nearest second
            # Calculate rallies in 30 minutes (max 5)
            rallies_30min = min(5, int(1800 // round_trip)) if round_trip > 0 else 0
            castle["rallies_30min"] = rallies_30min
        else:
            castle["round_trip"] = None
            castle["rallies_30min"] = 0


def update_castle_round_trip_time(castle: Dict, bear_traps: List[Dict]):
    """Update round trip time for a single castle.

    Args:
        castle: Castle dictionary
        bear_traps: List of bear trap dictionaries
    """
    round_trip = calculate_round_trip_time(castle, bear_traps)
    if round_trip is not None:
        castle["round_trip"] = round(round_trip)  # Round to nearest second
        # Calculate rallies in 30 minutes (max 5)
        rallies_30min = min(5, int(1800 // round_trip)) if round_trip > 0 else 0
        castle["rallies_30min"] = rallies_30min
    else:
        castle["round_trip"] = None
        castle["rallies_30min"] = 0
