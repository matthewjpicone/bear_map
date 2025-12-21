"""
Scoring module for Bear Map.

This module computes priority ranks and efficiency scores for castle placements.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
"""

import math
from statistics import median, quantiles
from typing import List, Dict, Tuple, Optional


# =========================
# Public: Priority Scoring
# =========================

def compute_priority(castles: List[Dict]) -> List[Dict]:
    """Compute priority scores and ranks for castles.

    Args:
        castles: List of castle dictionaries

    Returns:
        List of castles with added priority fields
    """
    if not castles:
        return []

    # Extract metrics
    powers = []
    player_levels = []
    cc_levels = []
    attendances = []

    for c in castles:
        power = math.log10(max(float(c.get("power", 0)), 1))
        powers.append(power)

        player_level = float(c.get("player_level", 0))
        player_levels.append(player_level)

        cc_level = float(c.get("command_centre_level", 0) or 0)
        cc_levels.append(cc_level)

        attendance = c.get("attendance")
        if attendance is not None:
            attendances.append(float(attendance))

    # Handle attendance median
    attendance_median = median(attendances) if attendances else 0.5

    # Compute percentiles for normalization
    def get_percentiles(values):
        if not values:
            return 0.5, 0.5
        sorted_vals = sorted(values)
        if len(sorted_vals) < 20:  # Rough estimate
            p05 = sorted_vals[0]
            p95 = sorted_vals[-1]
        else:
            p05 = quantiles(sorted_vals, n=20)[0]  # 5th percentile (ish)
            p95 = quantiles(sorted_vals, n=20)[-1]  # 95th percentile (ish)
        return p05, p95

    p05_power, p95_power = get_percentiles(powers)
    p05_pl, p95_pl = get_percentiles(player_levels)
    p05_cc, p95_cc = get_percentiles(cc_levels)
    p05_att, p95_att = get_percentiles(attendances) if attendances else (0.5, 0.5)

    def norm(x, p05, p95):
        if p95 == p05:
            return 0.5
        return max(0, min(1, (x - p05) / (p95 - p05)))

    # Compute for each castle
    for c in castles:
        power = math.log10(max(float(c.get("power", 0)), 1))
        n_power = norm(power, p05_power, p95_power)

        player_level = float(c.get("player_level", 0))
        n_player_level = norm(player_level, p05_pl, p95_pl)

        cc_level = float(c.get("command_centre_level", 0) or 0)
        if cc_level == 0:
            n_cc = 0.0
        else:
            n_cc = norm(cc_level, p05_cc, p95_cc)

        attendance = c.get("attendance")
        if attendance is None:
            n_attendance = norm(attendance_median, p05_att, p95_att)
        else:
            n_attendance = norm(float(attendance), p05_att, p95_att)

        priority_score = (
                0.50 * n_power +
                0.20 * n_player_level +
                0.20 * n_cc +
                0.10 * n_attendance
        )

        c["priority_score"] = priority_score
        c["priority_debug"] = {
            "n_power": n_power,
            "n_player_level": n_player_level,
            "n_cc": n_cc,
            "n_attendance": n_attendance,
            "p05_power": p05_power,
            "p95_power": p95_power,
            "p05_pl": p05_pl,
            "p95_pl": p95_pl,
            "p05_cc": p05_cc,
            "p95_cc": p95_cc,
            "p05_att": p05_att,
            "p95_att": p95_att,
            "attendance_median": attendance_median,
        }

    # Sort for ranking
    sorted_castles = sorted(
        castles,
        key=lambda c: (
            -c["priority_score"],
            -float(c.get("power", 0)),
            -float(c.get("player_level", 0)),
            c.get("id", ""),
        ),
    )

    N = len(castles)
    for idx, c in enumerate(sorted_castles):
        c["priority_index"] = idx
        if N == 1:
            rank = 1
        else:
            rank = 1 + round(99 * (idx / (N - 1)))
        c["priority_rank_100"] = rank

    return castles


# =========================
# Geometry / Tiles
# =========================

def chebyshev_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    """Chebyshev distance (max dx, dy)."""
    return max(abs(x1 - x2), abs(y1 - y2))


def get_walkable_tiles(grid_size: int, banners: List[Dict], bear_traps: List[Dict]) -> List[Tuple[int, int]]:
    """Get all walkable tiles, excluding banners and bear influence areas."""
    walkable: List[Tuple[int, int]] = []
    occupied = set()

    # Add banners
    for b in banners:
        bx, by = b.get("x"), b.get("y")
        if bx is not None and by is not None:
            occupied.add((bx, by))

    # Add bear influence (3x3 around each bear)
    for bear in bear_traps:
        bx, by = bear.get("x"), bear.get("y")
        if bx is None or by is None:
            continue
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                occupied.add((bx + dx, by + dy))

    for x in range(grid_size):
        for y in range(grid_size):
            if (x, y) not in occupied:
                walkable.append((x, y))

    return walkable


# =========================
# Internal Helpers (DRY)
# =========================

def _find_bear(bear_traps: List[Dict], bear_id: str) -> Optional[Dict]:
    return next((b for b in bear_traps if b.get("id") == bear_id), None)


def _has_xy(obj: Dict) -> bool:
    return obj.get("x") is not None and obj.get("y") is not None


def _normalize_preference(raw: Optional[str]) -> str:
    """Normalize preference string to canonical lowercase form.

    Canonical values: "bt1", "bt2", "bt1/2", "bt2/1"

    This is a local wrapper that imports from placement to maintain DRY.
    For direct use, import normalize_preference from placement.

    Args:
        raw: Raw preference string from config/user input.

    Returns:
        Normalized lowercase preference string.
    """
    # Import here to avoid circular imports
    from .placement import normalize_preference
    return normalize_preference(raw)


def _weighted_travel_time(pref_norm: str, dist_to_bear1: float, dist_to_bear2: float) -> float:
    if pref_norm == "bt1":
        return dist_to_bear1
    if pref_norm == "bt2":
        return dist_to_bear2
    if pref_norm == "bt2/1":
        return 0.7 * dist_to_bear2 + 0.3 * dist_to_bear1
    # default: bt1/2
    return 0.7 * dist_to_bear1 + 0.3 * dist_to_bear2


def _choose_first_available(tiles: List[Tuple[int, int]], occupied: set) -> Optional[Tuple[int, int]]:
    for t in tiles:
        if t not in occupied:
            return t
    return None


# =========================
# Ideal Allocation
# =========================

def compute_ideal_allocation(map_data: Dict, castles: List[Dict]) -> List[Dict]:
    """Compute ideal allocation for castles.

    Mutates castles in-place with:
      - ideal_x, ideal_y
      - ideal_travel_time
    """
    grid_size = map_data["grid_size"]
    banners = map_data.get("banners", [])
    bear_traps = map_data.get("bear_traps", [])

    walkable = get_walkable_tiles(grid_size, banners, bear_traps)

    bear1 = _find_bear(bear_traps, "Bear 1")
    bear2 = _find_bear(bear_traps, "Bear 2")

    if not bear1 or not bear2 or not _has_xy(bear1) or not _has_xy(bear2):
        # Cannot compute ideal without bears -> preserve non-breaking behaviour
        for c in castles:
            c["ideal_x"] = c.get("x", 0)
            c["ideal_y"] = c.get("y", 0)
            c["ideal_travel_time"] = 0
        return castles

    # Pre-sorted tiles by closeness
    tiles_bear1 = sorted(
        walkable,
        key=lambda t: chebyshev_distance(t[0], t[1], bear1["x"], bear1["y"]),
    )
    tiles_bear2 = sorted(
        walkable,
        key=lambda t: chebyshev_distance(t[0], t[1], bear2["x"], bear2["y"]),
    )

    # Spine tiles (2 columns), sorted by best of both bears
    mid = grid_size // 2
    spine_cols = [mid - 1, mid]
    tiles_spine = [t for t in walkable if t[0] in spine_cols]
    tiles_spine.sort(
        key=lambda t: min(
            chebyshev_distance(t[0], t[1], bear1["x"], bear1["y"]),
            chebyshev_distance(t[0], t[1], bear2["x"], bear2["y"]),
        )
    )

    occupied_ideal = set()

    # Sort castles by priority_score if present, otherwise stable fallback
    sorted_castles = sorted(castles, key=lambda c: -float(c.get("priority_score", 0)))

    for c in sorted_castles:
        pref = _normalize_preference(c.get("preference"))

        # If locked and placed -> keep ideal exactly where it is
        if c.get("locked") and _has_xy(c):
            ideal = (c["x"], c["y"])
            occupied_ideal.add(ideal)
            ideal_x, ideal_y = ideal
        else:
            ideal_xy: Optional[Tuple[int, int]] = None

            if pref == "bt1":
                ideal_xy = _choose_first_available(tiles_bear1, occupied_ideal)

            elif pref == "bt2":
                ideal_xy = _choose_first_available(tiles_bear2, occupied_ideal)

            elif pref == "bt1/2":
                # You already computed spine tiles; actually use them.
                ideal_xy = _choose_first_available(tiles_spine, occupied_ideal)

            else:  # bt2/1
                # For bt2/1 we can still prefer spine (shared) OR bear2-first.
                # Keeping it bear2-first maintains intent.
                ideal_xy = _choose_first_available(tiles_bear2, occupied_ideal)

            # Fallback: any walkable
            if ideal_xy is None:
                ideal_xy = _choose_first_available(walkable, occupied_ideal) or (0, 0)

            ideal_x, ideal_y = ideal_xy
            occupied_ideal.add((ideal_x, ideal_y))

        c["ideal_x"] = ideal_x
        c["ideal_y"] = ideal_y

        dist_to_bear1 = chebyshev_distance(ideal_x, ideal_y, bear1["x"], bear1["y"])
        dist_to_bear2 = chebyshev_distance(ideal_x, ideal_y, bear2["x"], bear2["y"])
        c["ideal_travel_time"] = _weighted_travel_time(pref, dist_to_bear1, dist_to_bear2)

    return castles


# =========================
# Efficiency
# =========================

def compute_efficiency_for_single_castle(
        castle: Dict,
        all_castles: List[Dict],
        bear_traps: List[Dict],
        grid_size: int,
) -> float:
    """Compute efficiency score for a single castle.

    Efficiency is based on comparing actual travel time to ideal travel time.
    Lower score = better efficiency.

    Returns:
        Efficiency score from 0 (best) to 100 (worst), floored to nearest integer.
    """
    actual = castle.get("actual_travel_time")
    ideal = castle.get("ideal_travel_time")

    if actual is None or ideal is None:
        return 50  # Default mid-range if data missing

    if ideal == 0:
        if actual == 0:
            return 0  # Perfect placement
        return 100  # Worst - should be at bear but isn't

    ratio = actual / ideal

    if ratio <= 1.0:
        return 0
    elif ratio >= 3.0:
        return 100
    else:
        return math.floor((ratio - 1.0) * 50)


def _compute_actual_travel_times(castles: List[Dict], bear1: Optional[Dict], bear2: Optional[Dict]) -> None:
    """Mutates castles in-place: sets actual_travel_time for placed castles."""
    if not bear1 or not bear2 or not _has_xy(bear1) or not _has_xy(bear2):
        return

    for c in castles:
        if not _has_xy(c):
            continue

        pref = _normalize_preference(c.get("preference"))
        dist_to_bear1 = chebyshev_distance(c["x"], c["y"], bear1["x"], bear1["y"])
        dist_to_bear2 = chebyshev_distance(c["x"], c["y"], bear2["x"], bear2["y"])
        c["actual_travel_time"] = _weighted_travel_time(pref, dist_to_bear1, dist_to_bear2)


def _compute_map_scores(config: Dict, castles: List[Dict], bear_traps: List[Dict], grid_size: int,
                        banners: List[Dict]) -> None:
    """Mutates config in-place with map score fields (no return)."""
    bear1 = _find_bear(bear_traps, "Bear 1")
    bear2 = _find_bear(bear_traps, "Bear 2")

    placed_castles = [c for c in castles if _has_xy(c)]

    avg_eff = (
        sum(float(c.get("efficiency_score", 0)) for c in placed_castles) / len(placed_castles)
        if placed_castles
        else 0
    )

    # Empty tiles score
    walkable = get_walkable_tiles(grid_size, banners, bear_traps)
    occupied_after = set()
    for c in placed_castles:
        # 2x2 castle footprint
        for dx in range(2):
            for dy in range(2):
                occupied_after.add((c["x"] + dx, c["y"] + dy))

    empty_tiles = [t for t in walkable if t not in occupied_after]

    empty_score_100 = 0
    if empty_tiles and bear1 and bear2 and _has_xy(bear1) and _has_xy(bear2):
        distances = [
            min(
                chebyshev_distance(t[0], t[1], bear1["x"], bear1["y"]),
                chebyshev_distance(t[0], t[1], bear2["x"], bear2["y"]),
            )
            for t in empty_tiles
        ]
        T_max = grid_size * 2
        q_values = [1 - min(1, d / T_max) for d in distances]
        empty_score_100 = round(100 * (sum(q_values) / len(q_values)))

    # Map score calculation (preserve your current formula)
    scaled_eff_900 = 9 * avg_eff * 0.9
    map_eff_component = 900 - scaled_eff_900
    empty_component_900 = 9 * empty_score_100
    map_score_900 = round(0.85 * map_eff_component + 0.15 * empty_component_900)
    map_score_percent = round(100 * map_score_900 / 900, 1)

    # Average round trip time (in seconds)
    round_trip_times = [
        c.get("round_trip", 0)
        for c in placed_castles
        if c.get("round_trip") is not None
           and c.get("round_trip") != "NA"
           and c.get("round_trip") > 0
    ]
    avg_round_trip = round(sum(round_trip_times) / len(round_trip_times)) if round_trip_times else 0

    # Average rallies per castle
    rallies = [c.get("rallies_30min", 0) for c in placed_castles]
    avg_rallies = round(sum(rallies) / len(rallies), 1) if rallies else 0

    config["map_score_900"] = map_score_900
    config["map_score_percent"] = map_score_percent
    config["empty_score_100"] = empty_score_100
    config["efficiency_avg"] = round(avg_eff, 1)
    config["avg_round_trip"] = avg_round_trip
    config["avg_rallies"] = avg_rallies


def compute_efficiency(config: Dict, castles: List[Dict]) -> List[Dict]:
    """Compute efficiency scores for all castles and update map score fields.

    Args:
        config: Configuration dictionary containing bear_traps and grid_size.
        castles: List of castle dictionaries.

    Returns:
        Updated list of castles with efficiency_score set.
    """
    bear_traps = config.get("bear_traps", [])
    grid_size = config.get("grid_size", 28)
    banners = config.get("banners", [])

    bear1 = _find_bear(bear_traps, "Bear 1")
    bear2 = _find_bear(bear_traps, "Bear 2")

    # 1) Compute actual_travel_time for placed castles
    _compute_actual_travel_times(castles, bear1, bear2)

    # 2) Compute efficiency_score for all castles (preserve your behaviour)
    for c in castles:
        if not _has_xy(c):
            c["efficiency_score"] = 100
            continue

        eff = compute_efficiency_for_single_castle(c, castles, bear_traps, grid_size)
        c["efficiency_score"] = eff

    # 3) Compute map score fields on config
    _compute_map_scores(config, castles, bear_traps, grid_size, banners)

    return castles
