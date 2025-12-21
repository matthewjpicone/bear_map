"""
Castle placement algorithms.

This module contains logic for automatically placing castles on the grid,
optimizing for spacing and avoiding overlaps.

Algorithm Overview:
- Phase 0: Setup (blocked tiles, valid tiles, occupied from locked)
- Phase 1: Group castles by preference, order committed-first
- Phase 2: Build distance-frontier queues (no slices)
- Phase 3: Place using scoring + compaction pass

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
Last Updated: 2025-12-21
"""

import math
from typing import List, Dict, Tuple, Optional, Set

from .config import load_config, save_config
from .scoring import (
    compute_priority,
    compute_efficiency,
    chebyshev_distance,
    compute_ideal_allocation,
)
from .validation import (
    check_castle_overlap,
    check_castle_overlap_with_entities,
    rectangles_overlap,
)

# =========================
# Module Constants
# =========================

# Packing weight for compactness scoring (higher = prefer tiles adjacent to existing castles)
PACK_WEIGHT = 2.5

# Hybrid anti-sniping: penalty if hybrid is within this radius of primary bear
HYBRID_NEAR_RADIUS = 4
HYBRID_NEAR_PENALTY = 50.0

# Round-trip target in seconds (6 minutes)
RT_TARGET = 360

# Compaction pass iterations
COMPACTION_PASSES = 5

# Debug flag for placement diagnostics
DEBUG = False


# =========================
# DRY Helper Functions
# =========================

def normalize_preference(raw: Optional[str]) -> str:
    """Normalize preference string to canonical lowercase form.

    Canonical values: "bt1", "bt2", "bt1/2", "bt2/1"

    Args:
        raw: Raw preference string from config/user input.

    Returns:
        Normalized lowercase preference string.
    """
    s = (raw or "").strip().lower()

    # BT1 variants
    if s in ("bt1", "b1", "bear 1", "bear1", "bear_1", "bear-1"):
        return "bt1"

    # BT2 variants
    if s in ("bt2", "b2", "bear 2", "bear2", "bear_2", "bear-2"):
        return "bt2"

    # BT2/1 explicit
    if s == "bt2/1":
        return "bt2/1"

    # Everything else (both, either, any, bt1/2, unknown) -> bt1/2
    return "bt1/2"


def primary_bear_id(pref_norm: str) -> str:
    """Get the primary bear ID for a normalized preference.

    Args:
        pref_norm: Normalized preference string.

    Returns:
        "Bear 1" or "Bear 2"
    """
    if pref_norm in ("bt2", "bt2/1"):
        return "Bear 2"
    return "Bear 1"


def _find_bear(bear_traps: List[Dict], bear_id: str) -> Optional[Dict]:
    """Find a bear trap by ID."""
    return next((b for b in bear_traps if b.get("id") == bear_id), None)


def _has_xy(obj: Dict) -> bool:
    """Check if an object has valid x,y coordinates."""
    return obj.get("x") is not None and obj.get("y") is not None


def euclidean_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate Euclidean distance between two points."""
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def round_trip_for_tile(tile_x: int, tile_y: int, bear_x: int, bear_y: int) -> float:
    """Calculate round trip time in seconds for a castle tile to a bear.

    Formula: 300 + 2 * (distance * 3)
    Base time: 300 seconds (5 minutes)
    Travel rate: 3 seconds per tile

    Args:
        tile_x, tile_y: Castle top-left coordinates.
        bear_x, bear_y: Bear coordinates.

    Returns:
        Round trip time in seconds.
    """
    castle_center_x = tile_x + 1
    castle_center_y = tile_y + 1
    bear_center_x = bear_x + 1
    bear_center_y = bear_y + 1

    distance = euclidean_distance(
        castle_center_x, castle_center_y,
        bear_center_x, bear_center_y
    )

    travel_rate = 3  # seconds per tile
    return 300 + 2 * (distance * travel_rate)


def weighted_travel_time(pref_norm: str, dist_to_bear1: float, dist_to_bear2: float) -> float:
    """Calculate weighted travel time based on preference."""
    if pref_norm == "bt1":
        return dist_to_bear1
    if pref_norm == "bt2":
        return dist_to_bear2
    if pref_norm == "bt2/1":
        return 0.7 * dist_to_bear2 + 0.3 * dist_to_bear1
    # bt1/2
    return 0.7 * dist_to_bear1 + 0.3 * dist_to_bear2


# =========================
# Tile Helpers
# =========================

def tile_free(x: int, y: int, occupied: Set[Tuple[int, int]]) -> bool:
    """Check if a 2x2 castle footprint is free of occupied tiles."""
    for dx in range(2):
        for dy in range(2):
            if (x + dx, y + dy) in occupied:
                return False
    return True


def mark_occupied(x: int, y: int, occupied: Set[Tuple[int, int]]) -> None:
    """Mark a 2x2 castle footprint as occupied."""
    for dx in range(2):
        for dy in range(2):
            occupied.add((x + dx, y + dy))


def unmark_occupied(x: int, y: int, occupied: Set[Tuple[int, int]]) -> None:
    """Unmark a 2x2 castle footprint from occupied."""
    for dx in range(2):
        for dy in range(2):
            occupied.discard((x + dx, y + dy))


def neighbor_contact_score(x: int, y: int, occupied: Set[Tuple[int, int]]) -> int:
    """Count occupied tiles in a 1-tile ring around a 2x2 castle footprint.

    Higher score = more contact with existing castles = better packing.
    """
    contact = 0
    for dx in range(-1, 3):
        for dy in range(-1, 3):
            if 0 <= dx <= 1 and 0 <= dy <= 1:
                continue  # Skip the castle's own footprint
            if (x + dx, y + dy) in occupied:
                contact += 1
    return contact


def preferred_parity(castles: List[Dict]) -> Tuple[int, int]:
    """Determine preferred (x%2, y%2) parity based on locked castle positions."""
    parity_counts = {(0, 0): 0, (0, 1): 0, (1, 0): 0, (1, 1): 0}

    for c in castles:
        if c.get("locked") and _has_xy(c):
            px = c["x"] % 2
            py = c["y"] % 2
            parity_counts[(px, py)] += 1

    max_count = max(parity_counts.values())
    for parity in [(0, 0), (0, 1), (1, 0), (1, 1)]:
        if parity_counts[parity] == max_count:
            return parity

    return (0, 0)


# =========================
# Phase 2: Queue Builders
# =========================

def build_bear_queue(
        all_valid_tiles: List[Tuple[int, int]],
        bear: Dict,
        other_bear: Optional[Dict],
        occupied: Set[Tuple[int, int]]
) -> List[Tuple[int, int]]:
    """Build a queue of tiles sorted by closeness to a bear (committed players).

    Primary: Chebyshev distance to bear (ascending)
    Secondary: neighbor contact (descending = more contact first)
    """
    if not bear or not _has_xy(bear):
        return list(all_valid_tiles)

    bx, by = bear["x"], bear["y"]

    def tile_key(tile: Tuple[int, int]) -> Tuple[int, int]:
        tx, ty = tile
        dist = chebyshev_distance(tx + 1, ty + 1, bx + 1, by + 1)
        contact = neighbor_contact_score(tx, ty, occupied)
        return (dist, -contact)

    return sorted(all_valid_tiles, key=tile_key)


def build_midline_queue(
        all_valid_tiles: List[Tuple[int, int]],
        bear1: Optional[Dict],
        bear2: Optional[Dict],
        pref_norm: str,
        occupied: Set[Tuple[int, int]]
) -> List[Tuple[int, int]]:
    """Build a queue for hybrid players (BT1/2, BT2/1).

    Primary: midline metric (abs(d1 - d2)) ascending
    Secondary: weighted travel based on preference
    Third: neighbor contact (descending)
    """
    if not bear1 or not bear2 or not _has_xy(bear1) or not _has_xy(bear2):
        return list(all_valid_tiles)

    b1x, b1y = bear1["x"], bear1["y"]
    b2x, b2y = bear2["x"], bear2["y"]

    def tile_key(tile: Tuple[int, int]) -> Tuple[float, float, int]:
        tx, ty = tile
        cx, cy = tx + 1, ty + 1  # Castle center

        d1 = chebyshev_distance(cx, cy, b1x + 1, b1y + 1)
        d2 = chebyshev_distance(cx, cy, b2x + 1, b2y + 1)

        midline = abs(d1 - d2)

        if pref_norm == "bt2/1":
            weighted = 0.7 * d2 + 0.3 * d1
        else:  # bt1/2
            weighted = 0.7 * d1 + 0.3 * d2

        contact = neighbor_contact_score(tx, ty, occupied)

        return (midline, weighted, -contact)

    return sorted(all_valid_tiles, key=tile_key)


# =========================
# Phase 3: Scoring Function
# =========================

def score_tile_v2(
        tile_x: int,
        tile_y: int,
        castle: Dict,
        bear1: Optional[Dict],
        bear2: Optional[Dict],
        pref_norm: str,
        occupied: Set[Tuple[int, int]],
        max_priority: float,
        is_committed: bool
) -> float:
    """Score a candidate tile for placement. Lower is better.

    Components:
    1. Travel penalty (quadratic above RT_TARGET, priority-weighted)
    2. Under-target bonus
    3. Packing bonus
    4. Hybrid anti-sniping penalty
    """
    score = 0.0

    # Determine primary bear
    if pref_norm in ("bt2", "bt2/1"):
        primary_bear = bear2
    else:
        primary_bear = bear1

    # Priority weight (1 to 5 scale)
    priority_score = float(castle.get("priority_score", 0))
    if max_priority > 0:
        priority_normalized = priority_score / max_priority
    else:
        priority_normalized = 0.5
    priority_weight = 1 + 4 * priority_normalized

    # Travel penalty
    if primary_bear and _has_xy(primary_bear):
        rt = round_trip_for_tile(tile_x, tile_y, primary_bear["x"], primary_bear["y"])
        over = max(0, rt - RT_TARGET)

        # Quadratic penalty weighted by priority
        travel_penalty = (over ** 2) * priority_weight * 0.01
        score += travel_penalty

        # Small bonus for being under target
        if rt <= RT_TARGET:
            score -= (RT_TARGET - rt) * 0.5

        # Hybrid anti-sniping: penalize if too close to primary bear
        if not is_committed:
            d_primary = chebyshev_distance(
                tile_x + 1, tile_y + 1,
                primary_bear["x"] + 1, primary_bear["y"] + 1
            )
            if d_primary <= HYBRID_NEAR_RADIUS:
                score += HYBRID_NEAR_PENALTY

    # Packing bonus (more contact = lower score)
    contact = neighbor_contact_score(tile_x, tile_y, occupied)
    score -= contact * PACK_WEIGHT

    return score


# =========================
# Phase 3: Compaction Pass
# =========================

def compact_layout(
        castles: List[Dict],
        all_valid_tiles: List[Tuple[int, int]],
        occupied: Set[Tuple[int, int]],
        bear1: Optional[Dict],
        bear2: Optional[Dict],
        max_priority: float
) -> int:
    """Run compaction passes to fill holes and reduce whitespace.

    Iterates over castles (low priority first) and tries to find
    improving moves that increase packing or reduce distance.

    Returns:
        Number of castles moved.
    """
    total_moves = 0

    # Get unlocked placed castles, sorted by priority ascending (low first)
    movable = [
        c for c in castles
        if not c.get("locked") and _has_xy(c)
    ]
    movable.sort(key=lambda c: float(c.get("priority_score", 0)))

    for _pass in range(COMPACTION_PASSES):
        pass_moves = 0

        for castle in movable:
            if not _has_xy(castle):
                continue

            pref_norm = normalize_preference(castle.get("preference"))
            is_committed = pref_norm in ("bt1", "bt2")

            current_x, current_y = castle["x"], castle["y"]

            # Current score
            current_score = score_tile_v2(
                current_x, current_y, castle, bear1, bear2,
                pref_norm, occupied, max_priority, is_committed
            )
            current_contact = neighbor_contact_score(current_x, current_y, occupied)

            # Temporarily remove from occupied
            unmark_occupied(current_x, current_y, occupied)

            best_tile = None
            best_score = current_score
            best_contact = current_contact

            # Try all valid free tiles
            for tile in all_valid_tiles:
                if not tile_free(tile[0], tile[1], occupied):
                    continue

                new_score = score_tile_v2(
                    tile[0], tile[1], castle, bear1, bear2,
                    pref_norm, occupied, max_priority, is_committed
                )
                new_contact = neighbor_contact_score(tile[0], tile[1], occupied)

                # Accept if: better score AND (more contact OR closer to bear)
                if new_score < best_score and new_contact >= best_contact:
                    best_score = new_score
                    best_contact = new_contact
                    best_tile = tile

            # Apply move or restore
            if best_tile and best_tile != (current_x, current_y):
                castle["x"] = best_tile[0]
                castle["y"] = best_tile[1]
                mark_occupied(best_tile[0], best_tile[1], occupied)
                pass_moves += 1
            else:
                # Restore original position
                mark_occupied(current_x, current_y, occupied)

        total_moves += pass_moves

        if pass_moves == 0:
            break  # No improvements, stop early

    return total_moves


# =========================
# Collision Resolution
# =========================

def is_castle_invalid(
        castle: Dict,
        all_castles: List[Dict],
        bear_traps: List[Dict],
        banners: List[Dict]
) -> bool:
    """Check if a castle is in an invalid position."""
    cx, cy = castle.get("x"), castle.get("y")
    if cx is None or cy is None:
        return False

    has_castle_overlap, _ = check_castle_overlap(cx, cy, all_castles, exclude_id=castle["id"])
    if has_castle_overlap:
        return True

    has_entity_overlap, _ = check_castle_overlap_with_entities(cx, cy, bear_traps, banners)
    if has_entity_overlap:
        return True

    return False


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
    """Push a single castle outward to avoid overlap with a position."""
    cx, cy = castle.get("x"), castle.get("y")
    if cx is None or cy is None:
        return

    dx = 1 if cx >= avoid_x else -1
    dy = 1 if cy >= avoid_y else -1
    step = 2

    for attempt in [
        (dx * step, 0), (0, dy * step), (dx * step, dy * step),
        (-dx * step, 0), (0, -dy * step), (dx * step, -dy * step),
        (-dx * step, dy * step), (-dx * step, -dy * step),
    ]:
        test_x = cx + attempt[0]
        test_y = cy + attempt[1]

        if not (0 <= test_x <= grid_size - 2 and 0 <= test_y <= grid_size - 2):
            continue

        has_castle_overlap, _ = check_castle_overlap(
            test_x, test_y, all_castles, exclude_id=castle["id"]
        )
        has_entity_overlap, _ = check_castle_overlap_with_entities(
            test_x, test_y, bear_traps, banners
        )

        if not has_castle_overlap and not has_entity_overlap:
            castle["x"] = test_x
            castle["y"] = test_y
            return


def resolve_all_collisions(
        castles: List[Dict],
        grid_size: int,
        bear_traps: List[Dict],
        banners: List[Dict]
):
    """Resolve all collisions by iteratively pushing invalid castles outward."""
    max_iterations = 100
    center_x, center_y = grid_size // 2, grid_size // 2

    for _ in range(max_iterations):
        invalid_castles = [
            c for c in castles
            if is_castle_invalid(c, castles, bear_traps, banners)
        ]
        if not invalid_castles:
            break

        for castle in invalid_castles:
            push_castle_outward(
                castle, center_x, center_y, castles, grid_size, bear_traps, banners
            )


def resolve_map_collisions(
        placed_x: int,
        placed_y: int,
        castles: List[Dict],
        grid_size: int,
        bear_traps: List[Dict],
        banners: List[Dict]
):
    """Resolve collisions after a specific placement."""
    for _ in range(100):
        invalid_castles = [
            c for c in castles
            if is_castle_invalid(c, castles, bear_traps, banners)
        ]
        if not invalid_castles:
            break

        for castle in invalid_castles:
            push_castle_outward(
                castle, placed_x, placed_y, castles, grid_size, bear_traps, banners
            )


def push_castles_outward(
        placed_castle_x: int,
        placed_castle_y: int,
        castles: List[Dict],
        grid_size: int,
        bear_traps: List[Dict],
        banners: List[Dict],
        exclude_id: str = None
) -> Tuple[bool, str]:
    """Push unlocked castles outward that would overlap with a newly placed castle."""
    overlapping_castles = []
    for castle in castles:
        if exclude_id and castle.get("id") == exclude_id:
            continue
        cx, cy = castle.get("x"), castle.get("y")
        if cx is None or cy is None:
            continue
        if rectangles_overlap(placed_castle_x, placed_castle_y, 2, 2, cx, cy, 2, 2):
            overlapping_castles.append(castle)

    locked_overlaps = [c for c in overlapping_castles if c.get("locked", False)]
    if locked_overlaps:
        return False, f"Cannot place: overlaps locked castle '{locked_overlaps[0]['id']}'"

    for castle in overlapping_castles:
        if castle.get("locked", False):
            continue
        push_castle_outward(
            castle, placed_castle_x, placed_castle_y,
            castles, grid_size, bear_traps, banners, exclude_id
        )

    return True, ""


def push_castles_away_from_bear(
        bear_x: int,
        bear_y: int,
        castles: List[Dict],
        grid_size: int,
        bear_traps: List[Dict],
        banners: List[Dict]
) -> Tuple[bool, str]:
    """Push unlocked castles away from a bear trap position."""
    overlapping_castles = []
    for castle in castles:
        cx, cy = castle.get("x"), castle.get("y")
        if cx is None or cy is None:
            continue
        if rectangles_overlap(cx, cy, 2, 2, bear_x - 1, bear_y - 1, 3, 3):
            overlapping_castles.append(castle)

    locked_overlaps = [c for c in overlapping_castles if c.get("locked", False)]
    if locked_overlaps:
        return False, f"Cannot place bear: overlaps locked castle '{locked_overlaps[0]['id']}'"

    # Temporarily add the new bear position (with id to avoid KeyError in validation)
    temp_bear_traps = bear_traps + [{"id": "temp_bear", "x": bear_x, "y": bear_y}]

    for castle in overlapping_castles:
        if castle.get("locked", False):
            continue
        push_castle_outward(
            castle, bear_x, bear_y, castles, grid_size, temp_bear_traps, banners
        )

    return True, ""


def move_castle_to_edge(
        castle: Dict,
        all_castles: List[Dict],
        grid_size: int,
        bear_traps: List[Dict],
        banners: List[Dict]
) -> bool:
    """Move a castle to the nearest edge of the map."""
    cx, cy = castle.get("x", 0) or 0, castle.get("y", 0) or 0

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
    else:
        target_x, target_y = cx, grid_size - 2

    has_castle_overlap, _ = check_castle_overlap(
        target_x, target_y, all_castles, exclude_id=castle["id"]
    )
    has_entity_overlap, _ = check_castle_overlap_with_entities(
        target_x, target_y, bear_traps, banners
    )

    if not has_castle_overlap and not has_entity_overlap:
        castle["x"] = target_x
        castle["y"] = target_y
        return True

    for edge_positions in [
        [(x, 0) for x in range(0, grid_size - 1, 2)],
        [(x, grid_size - 2) for x in range(0, grid_size - 1, 2)],
        [(0, y) for y in range(0, grid_size - 1, 2)],
        [(grid_size - 2, y) for y in range(0, grid_size - 1, 2)],
    ]:
        for pos_x, pos_y in edge_positions:
            has_castle_overlap, _ = check_castle_overlap(
                pos_x, pos_y, all_castles, exclude_id=castle["id"]
            )
            has_entity_overlap, _ = check_castle_overlap_with_entities(
                pos_x, pos_y, bear_traps, banners
            )
            if not has_castle_overlap and not has_entity_overlap:
                castle["x"] = pos_x
                castle["y"] = pos_y
                return True

    return False


# =========================
# Auto-Placement Algorithm
# =========================

async def auto_place_castles() -> Dict[str, int]:
    """Auto-place castles on the grid using committed-first ordering.

    Algorithm:
    - Phase 0: Setup (blocked tiles, valid tiles, occupied)
    - Phase 1: Group by preference, order committed-first by priority
    - Phase 2: Build distance-frontier queues (no slices)
    - Phase 3: Place using scoring + compaction pass

    Returns:
        Dictionary with success status and number of castles placed.
    """
    config = load_config()
    castles = config.get("castles", [])
    bear_traps = config.get("bear_traps", [])
    banners = config.get("banners", [])
    grid_size = config.get("grid_size", 28)

    # ========================================
    # PHASE 0: Setup
    # ========================================

    # Stage unlocked castles
    for c in castles:
        if not c.get("locked"):
            c["x"] = None
            c["y"] = None

    # Compute priority scores
    castles = compute_priority(castles)

    # Compute ideal allocation (for efficiency calculations later)
    compute_ideal_allocation(config, castles)

    # Get bears
    bear1 = _find_bear(bear_traps, "Bear 1")
    bear2 = _find_bear(bear_traps, "Bear 2")

    # Build static blocked tiles
    static_blocked: Set[Tuple[int, int]] = set()

    for banner in banners:
        bx, by = banner.get("x"), banner.get("y")
        if bx is not None and by is not None:
            static_blocked.add((bx, by))

    for bear in bear_traps:
        bx, by = bear.get("x"), bear.get("y")
        if bx is not None and by is not None:
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    static_blocked.add((bx + dx, by + dy))

    # Build all valid tile origins for 2x2 castles
    all_valid_tiles: List[Tuple[int, int]] = []
    for x in range(grid_size - 1):
        for y in range(grid_size - 1):
            blocked = False
            for dx in range(2):
                for dy in range(2):
                    if (x + dx, y + dy) in static_blocked:
                        blocked = True
                        break
                if blocked:
                    break
            if not blocked:
                all_valid_tiles.append((x, y))

    # Parity preference for reducing gaps
    px, py = preferred_parity(castles)
    parity_tiles = [t for t in all_valid_tiles if t[0] % 2 == px and t[1] % 2 == py]

    # Build occupied from locked castles
    occupied: Set[Tuple[int, int]] = set()
    for c in castles:
        if c.get("locked") and _has_xy(c):
            mark_occupied(c["x"], c["y"], occupied)

    # Get max priority for normalization
    max_priority = max(
        (float(c.get("priority_score", 0)) for c in castles),
        default=1.0
    ) or 1.0

    # ========================================
    # PHASE 1: Grouping + Ordering (Committed-First)
    # ========================================

    def castle_sort_key(c: Dict) -> Tuple:
        """Sort key: priority desc, then power, level, cc as tiebreakers."""
        return (
            -float(c.get("priority_score", 0)),
            -float(c.get("power", 0)),
            -float(c.get("player_level", 0)),
            -float(c.get("command_centre_level", 0) or 0),
        )

    # Group unlocked castles by preference
    g_bt1 = []
    g_bt2 = []
    g_bt12 = []
    g_bt21 = []

    for c in castles:
        if c.get("locked"):
            continue
        pref = normalize_preference(c.get("preference"))
        if pref == "bt1":
            g_bt1.append(c)
        elif pref == "bt2":
            g_bt2.append(c)
        elif pref == "bt2/1":
            g_bt21.append(c)
        else:  # bt1/2
            g_bt12.append(c)

    # Sort each group by priority
    g_bt1.sort(key=castle_sort_key)
    g_bt2.sort(key=castle_sort_key)
    g_bt12.sort(key=castle_sort_key)
    g_bt21.sort(key=castle_sort_key)

    # Placement order: BT1 -> BT2 -> BT1/2 -> BT2/1
    placement_order = g_bt1 + g_bt2 + g_bt12 + g_bt21

    if DEBUG:
        print(f"[DEBUG] Groups: BT1={len(g_bt1)}, BT2={len(g_bt2)}, "
              f"BT1/2={len(g_bt12)}, BT2/1={len(g_bt21)}")

    # ========================================
    # PHASE 2 & 3: Placement with Distance Queues
    # ========================================

    placed_count = 0

    for castle in placement_order:
        pref_norm = normalize_preference(castle.get("preference"))
        is_committed = pref_norm in ("bt1", "bt2")

        # Build appropriate queue
        if pref_norm == "bt1":
            queue = build_bear_queue(all_valid_tiles, bear1, bear2, occupied)
        elif pref_norm == "bt2":
            queue = build_bear_queue(all_valid_tiles, bear2, bear1, occupied)
        else:
            queue = build_midline_queue(all_valid_tiles, bear1, bear2, pref_norm, occupied)

        # Prefer parity-aligned tiles
        parity_queue = [t for t in queue if t[0] % 2 == px and t[1] % 2 == py]

        # Find best tile
        best_tile = None
        best_score = float("inf")

        # Try parity tiles first
        for tile in parity_queue:
            if not tile_free(tile[0], tile[1], occupied):
                continue

            score = score_tile_v2(
                tile[0], tile[1], castle, bear1, bear2,
                pref_norm, occupied, max_priority, is_committed
            )

            if score < best_score:
                best_score = score
                best_tile = tile
                # Early exit for committed players finding good tiles
                if is_committed and score < 0:
                    break

        # Fallback to all tiles if no parity tile found
        if best_tile is None:
            for tile in queue:
                if not tile_free(tile[0], tile[1], occupied):
                    continue

                score = score_tile_v2(
                    tile[0], tile[1], castle, bear1, bear2,
                    pref_norm, occupied, max_priority, is_committed
                )

                if score < best_score:
                    best_score = score
                    best_tile = tile

        # Place the castle
        if best_tile:
            castle["x"] = best_tile[0]
            castle["y"] = best_tile[1]
            mark_occupied(best_tile[0], best_tile[1], occupied)
            placed_count += 1

    # ========================================
    # PHASE 3b: Compaction Pass
    # ========================================

    compaction_moves = compact_layout(
        castles, all_valid_tiles, occupied, bear1, bear2, max_priority
    )

    if DEBUG:
        print(f"[DEBUG] Compaction moved {compaction_moves} castles")

    # ========================================
    # Finalization
    # ========================================

    # Resolve any remaining collisions
    resolve_all_collisions(castles, grid_size, bear_traps, banners)

    # Update round trip times
    update_all_round_trip_times(castles, bear_traps)

    # Compute efficiency scores
    compute_efficiency(config, castles)

    # Save config
    save_config(config)

    # ========================================
    # Verification + Debug Output
    # ========================================

    overlaps_found = False
    for i, c1 in enumerate(castles):
        if not _has_xy(c1):
            continue
        for c2 in castles[i + 1:]:
            if not _has_xy(c2):
                continue
            if rectangles_overlap(c1["x"], c1["y"], 2, 2, c2["x"], c2["y"], 2, 2):
                print(f"Overlap detected: {c1['id']} and {c2['id']}")
                overlaps_found = True

        has_entity_overlap, entity_id = check_castle_overlap_with_entities(
            c1["x"], c1["y"], bear_traps, banners
        )
        if has_entity_overlap:
            print(f"Castle {c1['id']} overlaps with {entity_id}")
            overlaps_found = True

    if DEBUG:
        # Compute metrics
        placed_castles = [c for c in castles if _has_xy(c)]
        rt_values = [c.get("round_trip", 999) for c in placed_castles if c.get("round_trip")]
        under_360 = sum(1 for rt in rt_values if rt <= 360)
        pct_under = (under_360 / len(rt_values) * 100) if rt_values else 0

        bt1_rts = [c.get("round_trip", 999) for c in g_bt1 if _has_xy(c) and c.get("round_trip")]
        bt2_rts = [c.get("round_trip", 999) for c in g_bt2 if _has_xy(c) and c.get("round_trip")]

        def percentile(vals, p):
            if not vals:
                return 0
            vals = sorted(vals)
            idx = int(len(vals) * p / 100)
            return vals[min(idx, len(vals) - 1)]

        print(f"[DEBUG] Placed: {placed_count}")
        print(f"[DEBUG] RT <= 360s: {under_360}/{len(rt_values)} ({pct_under:.1f}%)")
        if bt1_rts:
            print(f"[DEBUG] BT1 RT p50={percentile(bt1_rts, 50)}, p90={percentile(bt1_rts, 90)}")
        if bt2_rts:
            print(f"[DEBUG] BT2 RT p50={percentile(bt2_rts, 50)}, p90={percentile(bt2_rts, 90)}")

        # Count hybrids near bears
        near_bear = 0
        for c in g_bt12 + g_bt21:
            if not _has_xy(c):
                continue
            for bear in [bear1, bear2]:
                if bear and _has_xy(bear):
                    d = chebyshev_distance(c["x"] + 1, c["y"] + 1, bear["x"] + 1, bear["y"] + 1)
                    if d <= HYBRID_NEAR_RADIUS:
                        near_bear += 1
                        break
        print(f"[DEBUG] Hybrids within radius {HYBRID_NEAR_RADIUS} of bears: {near_bear}")

    if overlaps_found:
        print("Warning: Overlaps found after autoplace")
    else:
        print("Autoplace completed without overlaps")

    return {"success": True, "placed": placed_count}


def compute_efficiency_for_castle(
        castle: Dict,
        all_castles: List[Dict],
        bear_traps: List[Dict],
        grid_size: int
) -> float:
    """Compute efficiency score for a single castle.

    DEPRECATED: Use scoring.compute_efficiency_for_single_castle instead.
    """
    from .scoring import compute_efficiency_for_single_castle
    return compute_efficiency_for_single_castle(castle, all_castles, bear_traps, grid_size)


# =========================
# Round Trip Time Calculations
# =========================

def calculate_euclidean_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate Euclidean distance between two points."""
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def calculate_travel_time(distance: float) -> float:
    """Calculate travel time for a given distance. Rate: 3 seconds per tile."""
    return distance * 3.0


def calculate_round_trip_time(castle: Dict, bear_traps: List[Dict]) -> Optional[float]:
    """Calculate round trip time for a castle to its primary bear trap.

    BT1, BT1/2 -> Calculate to Bear 1 only
    BT2, BT2/1 -> Calculate to Bear 2 only
    """
    pref_norm = normalize_preference(castle.get("preference"))
    bear_id = primary_bear_id(pref_norm)
    bear = _find_bear(bear_traps, bear_id)

    if not bear or not _has_xy(bear):
        return None

    return calculate_single_round_trip(castle, bear)


def calculate_single_round_trip(castle: Dict, bear: Dict) -> Optional[float]:
    """Calculate round trip time for a castle to a specific bear."""
    if not _has_xy(castle) or not _has_xy(bear):
        return None

    castle_center_x = castle["x"] + 1
    castle_center_y = castle["y"] + 1
    bear_center_x = bear["x"] + 1
    bear_center_y = bear["y"] + 1

    distance = calculate_euclidean_distance(
        castle_center_x, castle_center_y,
        bear_center_x, bear_center_y
    )

    travel_time = calculate_travel_time(distance)
    base_time = 300  # 5 minutes
    return base_time + 2 * travel_time


def update_all_round_trip_times(castles: List[Dict], bear_traps: List[Dict]):
    """Update round trip times for all castles."""
    for castle in castles:
        update_castle_round_trip_time(castle, bear_traps)


def update_castle_round_trip_time(castle: Dict, bear_traps: List[Dict]):
    """Update round trip time for a single castle."""
    round_trip = calculate_round_trip_time(castle, bear_traps)
    if round_trip is not None:
        castle["round_trip"] = round(round_trip)
        castle["rallies_30min"] = min(5, int(1800 // round_trip)) if round_trip > 0 else 0
    else:
        castle["round_trip"] = None
        castle["rallies_30min"] = 0


# =========================
# Legacy Compatibility
# =========================

def build_slices(grid_size: int) -> Dict[str, List[int]]:
    """Build column slices (legacy, kept for compatibility but not used in placement)."""
    mid = grid_size // 2
    quarter = grid_size // 4
    return {
        "bt1": list(range(0, mid - quarter)),
        "bt1/2": list(range(mid - quarter - 2, mid + 2)),
        "bt2/1": list(range(mid - 2, mid + quarter + 2)),
        "bt2": list(range(mid + quarter, grid_size)),
    }


def get_spill_order(pref_norm: str) -> List[str]:
    """Get preference spill order (legacy, kept for compatibility)."""
    if pref_norm == "bt1":
        return ["bt1", "bt1/2", "bt2/1", "bt2"]
    if pref_norm == "bt2":
        return ["bt2", "bt2/1", "bt1/2", "bt1"]
    if pref_norm == "bt1/2":
        return ["bt1/2", "bt1", "bt2/1", "bt2"]
    return ["bt2/1", "bt2", "bt1/2", "bt1"]


def score_tile(
        tile_x: int,
        tile_y: int,
        castle: Dict,
        bear1: Optional[Dict],
        bear2: Optional[Dict],
        pref_norm: str,
        occupied: Set[Tuple[int, int]]
) -> float:
    """Score a tile (legacy wrapper for compatibility)."""
    max_priority = 1.0
    is_committed = pref_norm in ("bt1", "bt2")
    return score_tile_v2(
        tile_x, tile_y, castle, bear1, bear2,
        pref_norm, occupied, max_priority, is_committed
    )
