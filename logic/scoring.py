"""
Scoring module for Bear Map.

This module computes priority ranks and efficiency scores for castle placements.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
"""

import math
from typing import List, Dict, Tuple, Optional
from statistics import median, quantiles


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
        power = math.log10(max(float(c.get('power', 0)), 1))
        powers.append(power)

        player_level = float(c.get('player_level', 0))
        player_levels.append(player_level)

        cc_level = float(c.get('command_centre_level', 0) or 0)
        cc_levels.append(cc_level)

        attendance = c.get('attendance')
        if attendance is not None:
            attendances.append(float(attendance))

    # Handle attendance median
    if attendances:
        attendance_median = median(attendances)
    else:
        attendance_median = 0.5

    # Compute percentiles for normalization
    def get_percentiles(values):
        if not values:
            return 0.5, 0.5
        sorted_vals = sorted(values)
        if len(sorted_vals) < 20:  # Rough estimate
            p05 = sorted_vals[0]
            p95 = sorted_vals[-1]
        else:
            p05 = quantiles(sorted_vals, n=20)[0]  # 5th percentile
            p95 = quantiles(sorted_vals, n=20)[-1]  # 95th
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
        power = math.log10(max(float(c.get('power', 0)), 1))
        n_power = norm(power, p05_power, p95_power)

        player_level = float(c.get('player_level', 0))
        n_player_level = norm(player_level, p05_pl, p95_pl)

        cc_level = float(c.get('command_centre_level', 0) or 0)
        if cc_level == 0:
            n_cc = 0.0
        else:
            n_cc = norm(cc_level, p05_cc, p95_cc)

        attendance = c.get('attendance')
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

        c['priority_score'] = priority_score
        c['priority_debug'] = {
            'n_power': n_power,
            'n_player_level': n_player_level,
            'n_cc': n_cc,
            'n_attendance': n_attendance,
            'p05_power': p05_power,
            'p95_power': p95_power,
            'p05_pl': p05_pl,
            'p95_pl': p95_pl,
            'p05_cc': p05_cc,
            'p95_cc': p95_cc,
            'p05_att': p05_att,
            'p95_att': p95_att,
            'attendance_median': attendance_median
        }

    # Sort for ranking
    sorted_castles = sorted(castles, key=lambda c: (
        -c['priority_score'],
        -float(c.get('power', 0)),
        -float(c.get('player_level', 0)),
        c['id']
    ))

    N = len(castles)
    for idx, c in enumerate(sorted_castles):
        c['priority_index'] = idx
        if N == 1:
            rank = 1
        else:
            rank = 1 + round(99 * (idx / (N - 1)))
        c['priority_rank_100'] = rank

    return castles


def chebyshev_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    """Chebyshev distance (max dx, dy)."""
    return max(abs(x1 - x2), abs(y1 - y2))


def get_walkable_tiles(grid_size: int, banners: List[Dict], bear_traps: List[Dict]) -> List[Tuple[int, int]]:
    """Get all walkable tiles, excluding banners and bear influence areas."""
    walkable = []
    occupied = set()

    # Add banners
    for b in banners:
        if b.get('x') is not None and b.get('y') is not None:
            occupied.add((b['x'], b['y']))

    # Add bear influence (3x3 around each bear)
    for bear in bear_traps:
        bx, by = bear.get('x'), bear.get('y')
        if bx is not None and by is not None:
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    occupied.add((bx + dx, by + dy))

    for x in range(grid_size):
        for y in range(grid_size):
            if (x, y) not in occupied:
                walkable.append((x, y))

    return walkable


def compute_ideal_allocation(map_data: Dict, castles: List[Dict]) -> List[Dict]:
    """Compute ideal allocation for castles."""
    grid_size = map_data['grid_size']
    banners = map_data.get('banners', [])
    bear_traps = map_data.get('bear_traps', [])

    walkable = get_walkable_tiles(grid_size, banners, bear_traps)

    # Find bears
    bear1 = next((b for b in bear_traps if b['id'] == 'Bear 1'), None)
    bear2 = next((b for b in bear_traps if b['id'] == 'Bear 2'), None)

    if not bear1 or not bear2:
        # Cannot compute ideal without bears
        for c in castles:
            c['ideal_x'] = c.get('x', 0)
            c['ideal_y'] = c.get('y', 0)
            c['ideal_travel_time'] = 0
        return castles

    # Define zones
    tiles_bear1 = sorted(walkable, key=lambda t: chebyshev_distance(t[0], t[1], bear1['x'], bear1['y']))
    tiles_bear2 = sorted(walkable, key=lambda t: chebyshev_distance(t[0], t[1], bear2['x'], bear2['y']))

    mid = grid_size // 2
    spine_cols = [mid - 1, mid]
    tiles_spine = [t for t in walkable if t[0] in spine_cols]
    tiles_spine.sort(key=lambda t: min(
        chebyshev_distance(t[0], t[1], bear1['x'], bear1['y']),
        chebyshev_distance(t[0], t[1], bear2['x'], bear2['y'])
    ))

    # Occupied for ideal
    occupied_ideal = set()

    # Sort castles by priority
    sorted_castles = sorted(castles, key=lambda c: -c['priority_score'])

    for c in sorted_castles:
        pref = c.get('preference', 'BT1/2').lower()
        if pref not in ['bt1', 'bt2', 'bt1/2', 'bt2/1']:
            pref = 'bt1/2'

        # Check if locked and placed
        if c.get('locked') and c.get('x') is not None and c.get('y') is not None:
            ideal_x, ideal_y = c['x'], c['y']
            occupied_ideal.add((ideal_x, ideal_y))
        else:
            if pref == 'bt1':
                candidates = [t for t in tiles_bear1 if t not in occupied_ideal]
                if candidates:
                    ideal_x, ideal_y = candidates[0]
                else:
                    # Fallback to any
                    candidates = [t for t in walkable if t not in occupied_ideal]
                    ideal_x, ideal_y = candidates[0] if candidates else (0, 0)
            elif pref == 'bt2':
                candidates = [t for t in tiles_bear2 if t not in occupied_ideal]
                if candidates:
                    ideal_x, ideal_y = candidates[0]
                else:
                    candidates = [t for t in walkable if t not in occupied_ideal]
                    ideal_x, ideal_y = candidates[0] if candidates else (0, 0)
            elif pref == 'bt1/2':
                # Primary Bear 1, secondary Bear 2 - prefer tiles closer to Bear 1
                # but also reasonably close to Bear 2
                available = [t for t in walkable if t not in occupied_ideal]
                if available:
                    # Score: 70% weight on Bear 1 distance, 30% on Bear 2
                    scored = [(t, 0.7 * chebyshev_distance(t[0], t[1], bear1['x'], bear1['y']) +
                                  0.3 * chebyshev_distance(t[0], t[1], bear2['x'], bear2['y']))
                              for t in available]
                    ideal_x, ideal_y = min(scored, key=lambda x: x[1])[0]
                else:
                    ideal_x, ideal_y = 0, 0
            else:  # bt2/1
                # Primary Bear 2, secondary Bear 1 - prefer tiles closer to Bear 2
                # but also reasonably close to Bear 1
                available = [t for t in walkable if t not in occupied_ideal]
                if available:
                    # Score: 70% weight on Bear 2 distance, 30% on Bear 1
                    scored = [(t, 0.7 * chebyshev_distance(t[0], t[1], bear2['x'], bear2['y']) +
                                  0.3 * chebyshev_distance(t[0], t[1], bear1['x'], bear1['y']))
                              for t in available]
                    ideal_x, ideal_y = min(scored, key=lambda x: x[1])[0]
                else:
                    ideal_x, ideal_y = 0, 0

            occupied_ideal.add((ideal_x, ideal_y))

        c['ideal_x'] = ideal_x
        c['ideal_y'] = ideal_y

        # Compute ideal travel time with weighted scoring
        dist_to_bear1 = chebyshev_distance(ideal_x, ideal_y, bear1['x'], bear1['y'])
        dist_to_bear2 = chebyshev_distance(ideal_x, ideal_y, bear2['x'], bear2['y'])

        if pref == 'bt1':
            ideal_travel_time = dist_to_bear1
        elif pref == 'bt2':
            ideal_travel_time = dist_to_bear2
        elif pref == 'bt1/2':
            ideal_travel_time = 0.7 * dist_to_bear1 + 0.3 * dist_to_bear2
        else:  # bt2/1
            ideal_travel_time = 0.7 * dist_to_bear2 + 0.3 * dist_to_bear1
        c['ideal_travel_time'] = ideal_travel_time

    return castles

def compute_efficiency_for_single_castle(
    castle: Dict,
    all_castles: List[Dict],
    bear_traps: List[Dict],
    grid_size: int
) -> float:
    """Compute efficiency score for a single castle.

    Efficiency is based on comparing actual travel time to ideal travel time.
    Lower score = better efficiency.

    Args:
        castle: The castle to compute efficiency for.
        all_castles: List of all castles (for context).
        bear_traps: List of bear trap positions.
        grid_size: Size of the grid.

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

    # Ratio of actual to ideal (1.0 = perfect, higher = worse)
    ratio = actual / ideal

    # Convert ratio to 0-100 score
    # ratio 1.0 -> score 0 (perfect)
    # ratio 2.0 -> score 50
    # ratio 3.0+ -> score 100
    if ratio <= 1.0:
        return 0
    elif ratio >= 3.0:
        return 100
    else:
        return math.floor((ratio - 1.0) * 50)  # Floor to nearest integer

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

    bear1 = next((b for b in bear_traps if b.get("id") == "Bear 1"), None)
    bear2 = next((b for b in bear_traps if b.get("id") == "Bear 2"), None)

    # Compute actual_travel_time for ALL castles (including locked)
    for c in castles:
        if c.get("x") is None or c.get("y") is None:
            continue  # Skip unplaced castles, but NOT locked castles

        pref = c.get("preference", "BT1/2").lower()

        if bear1 and bear1.get("x") is not None and bear2 and bear2.get("x") is not None:
            dist_to_bear1 = chebyshev_distance(c["x"], c["y"], bear1["x"], bear1["y"])
            dist_to_bear2 = chebyshev_distance(c["x"], c["y"], bear2["x"], bear2["y"])

            if pref == "bt1":
                c["actual_travel_time"] = dist_to_bear1
            elif pref == "bt2":
                c["actual_travel_time"] = dist_to_bear2
            elif pref == "bt1/2":
                c["actual_travel_time"] = 0.7 * dist_to_bear1 + 0.3 * dist_to_bear2
            else:  # bt2/1
                c["actual_travel_time"] = 0.7 * dist_to_bear2 + 0.3 * dist_to_bear1

    # Compute efficiency for ALL placed castles (including locked)
    for castle in castles:
        if castle.get("x") is None or castle.get("y") is None:
            castle["efficiency_score"] = 100  # Unplaced gets worst score
            continue

        # Calculate efficiency regardless of lock status
        eff = compute_efficiency_for_single_castle(castle, castles, bear_traps, grid_size)
        castle["efficiency_score"] = eff

    # Calculate map score fields
    placed_castles = [c for c in castles if c.get("x") is not None and c.get("y") is not None]

    # Average efficiency
    avg_eff = sum(c.get("efficiency_score", 0) for c in placed_castles) / len(placed_castles) if placed_castles else 0

    # Calculate empty tiles score
    walkable = get_walkable_tiles(grid_size, banners, bear_traps)
    occupied_after = set()
    for c in placed_castles:
        for dx in range(2):
            for dy in range(2):
                occupied_after.add((c["x"] + dx, c["y"] + dy))

    empty_tiles = [t for t in walkable if t not in occupied_after]
    empty_score_100 = 0
    if empty_tiles and bear1 and bear2:
        distances = [
            min(chebyshev_distance(t[0], t[1], bear1["x"], bear1["y"]),
                chebyshev_distance(t[0], t[1], bear2["x"], bear2["y"]))
            for t in empty_tiles
        ]
        T_max = grid_size * 2
        q_values = [1 - min(1, d / T_max) for d in distances]
        empty_score_100 = round(100 * (sum(q_values) / len(q_values)))

    # Map score calculation
    scaled_eff_900 = 9 * avg_eff * 0.9
    map_eff_component = 900 - scaled_eff_900
    empty_component_900 = 9 * empty_score_100
    map_score_900 = round(0.85 * map_eff_component + 0.15 * empty_component_900)
    map_score_percent = round(100 * map_score_900 / 900, 1)

    # Calculate average round trip time (in seconds)
    round_trip_times = [c.get("round_trip", 0) for c in placed_castles
                        if c.get("round_trip") is not None and c.get("round_trip") != "NA" and c.get("round_trip") > 0]
    avg_round_trip = round(sum(round_trip_times) / len(round_trip_times)) if round_trip_times else 0

    # Calculate average rallies per castle
    rallies = [c.get("rallies_30min", 0) for c in placed_castles]
    avg_rallies = round(sum(rallies) / len(rallies), 1) if rallies else 0

    # Persist to config
    config["map_score_900"] = map_score_900
    config["map_score_percent"] = map_score_percent
    config["empty_score_100"] = empty_score_100
    config["efficiency_avg"] = round(avg_eff, 1)
    config["avg_round_trip"] = avg_round_trip
    config["avg_rallies"] = avg_rallies

    return castles
