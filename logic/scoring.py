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
        pref = c.get('preference', 'both').lower()
        if pref not in ['bear 1', 'bear 2', 'both']:
            pref = 'both'

        # Check if locked and placed
        if c.get('locked') and c.get('x') is not None and c.get('y') is not None:
            ideal_x, ideal_y = c['x'], c['y']
            occupied_ideal.add((ideal_x, ideal_y))
        else:
            if pref == 'bear 1':
                candidates = [t for t in tiles_bear1 if t not in occupied_ideal]
                if candidates:
                    ideal_x, ideal_y = candidates[0]
                else:
                    # Fallback to any
                    candidates = [t for t in walkable if t not in occupied_ideal]
                    ideal_x, ideal_y = candidates[0] if candidates else (0, 0)
            elif pref == 'bear 2':
                candidates = [t for t in tiles_bear2 if t not in occupied_ideal]
                if candidates:
                    ideal_x, ideal_y = candidates[0]
                else:
                    candidates = [t for t in walkable if t not in occupied_ideal]
                    ideal_x, ideal_y = candidates[0] if candidates else (0, 0)
            else:  # both
                candidates = [t for t in tiles_spine if t not in occupied_ideal]
                if candidates:
                    ideal_x, ideal_y = candidates[0]
                else:
                    # Best of bear1 or bear2
                    all_candidates = [(t, min(
                        chebyshev_distance(t[0], t[1], bear1['x'], bear1['y']),
                        chebyshev_distance(t[0], t[1], bear2['x'], bear2['y'])
                    )) for t in walkable if t not in occupied_ideal]
                    if all_candidates:
                        ideal_x, ideal_y = min(all_candidates, key=lambda x: x[1])[0]
                    else:
                        ideal_x, ideal_y = 0, 0

            occupied_ideal.add((ideal_x, ideal_y))

        c['ideal_x'] = ideal_x
        c['ideal_y'] = ideal_y

        # Compute ideal travel time
        if pref == 'bear 1':
            ideal_travel_time = chebyshev_distance(ideal_x, ideal_y, bear1['x'], bear1['y'])
        elif pref == 'bear 2':
            ideal_travel_time = chebyshev_distance(ideal_x, ideal_y, bear2['x'], bear2['y'])
        else:
            ideal_travel_time = min(
                chebyshev_distance(ideal_x, ideal_y, bear1['x'], bear1['y']),
                chebyshev_distance(ideal_x, ideal_y, bear2['x'], bear2['y'])
            )
        c['ideal_travel_time'] = ideal_travel_time

    return castles


def compute_efficiency(map_data: Dict, castles: List[Dict]) -> List[Dict]:
    """Compute efficiency scores for castles."""
    bear_traps = map_data.get('bear_traps', [])
    bear1 = next((b for b in bear_traps if b['id'] == 'Bear 1'), None)
    bear2 = next((b for b in bear_traps if b['id'] == 'Bear 2'), None)

    if not bear1 or not bear2:
        # Set defaults
        for c in castles:
            c['actual_travel_time'] = 0
            c['regret'] = 0
            c['block_penalty_raw'] = 0
            c['efficiency_score'] = 0
        return castles

    # Compute ideal allocation
    castles = compute_ideal_allocation(map_data, castles)

    # Compute actual travel times
    for c in castles:
        x, y = c.get('x'), c.get('y')
        if x is None or y is None:
            c['actual_travel_time'] = c['ideal_travel_time'] + 100  # Bad score
        else:
            pref = c.get('preference', 'both').lower()
            if pref == 'bear 1':
                actual = chebyshev_distance(x, y, bear1['x'], bear1['y'])
            elif pref == 'bear 2':
                actual = chebyshev_distance(x, y, bear2['x'], bear2['y'])
            else:
                actual = min(
                    chebyshev_distance(x, y, bear1['x'], bear1['y']),
                    chebyshev_distance(x, y, bear2['x'], bear2['y'])
                )
            c['actual_travel_time'] = actual

    # Regrets
    regrets = []
    for c in castles:
        regret = max(0, c['actual_travel_time'] - c['ideal_travel_time'])
        c['regret'] = regret
        if regret > 0:
            regrets.append(regret)

    # Tscale
    if regrets:
        Tscale = sorted(regrets)[int(len(regrets) * 0.9)] if len(regrets) >= 10 else max(regrets)
    else:
        Tscale = 1

    # Blocking penalty
    # Group by preference
    groups = {'bear 1': [], 'bear 2': [], 'both': []}
    for c in castles:
        pref = c.get('preference', 'both').lower()
        if pref not in groups:
            pref = 'both'
        groups[pref].append(c)

    for group_name, group in groups.items():
        if not group:
            continue
        # Sort by priority rank (lower rank is better)
        group_sorted = sorted(group, key=lambda c: c['priority_rank_100'])
        for i, ci in enumerate(group_sorted):
            block = 0
            for j, cj in enumerate(group_sorted):
                if j >= i:  # Only lower priority
                    continue
                if ci['actual_travel_time'] < cj['actual_travel_time']:
                    rank_diff = ci['priority_rank_100'] - cj['priority_rank_100']
                    if rank_diff > 0:
                        sigmoid_val = 1 / (1 + math.exp(-(rank_diff - 10) / 5))
                        block += (cj['actual_travel_time'] - ci['actual_travel_time']) * sigmoid_val
            ci['block_penalty_raw'] = block

    # Normalize block
    block_values = [c.get('block_penalty_raw', 0) for c in castles]
    if block_values:
        block_p90 = sorted(block_values)[int(len(block_values) * 0.9)] if len(block_values) >= 10 else max(block_values)
        block_p90 = max(block_p90, 1e-6)
    else:
        block_p90 = 1

    for c in castles:
        block_raw = c.get('block_penalty_raw', 0)
        block_norm = min(1, block_raw / block_p90)
        base = min(1, c['regret'] / Tscale)
        eff = 100 * (0.75 * base + 0.25 * block_norm)
        c['efficiency_score'] = round(eff)

    return castles
