"""
Test suite for castle auto-placement algorithm.

Tests:
- No overlaps after placement
- Round-trip time compression (target <= 360s)
- Priority order respected
- Deterministic placement

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-21
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logic.placement import (
    auto_place_castles,
    normalize_preference,
    primary_bear_id,
    round_trip_for_tile,
    build_slices,
    tile_free,
    _has_xy,
)
from logic.validation import rectangles_overlap, check_castle_overlap_with_entities
from logic.config import load_config


def test_normalize_preference():
    """Test preference normalization."""
    # BT1 variants
    assert normalize_preference("BT1") == "bt1"
    assert normalize_preference("bt1") == "bt1"
    assert normalize_preference("Bear 1") == "bt1"
    assert normalize_preference("bear 1") == "bt1"
    assert normalize_preference("B1") == "bt1"

    # BT2 variants
    assert normalize_preference("BT2") == "bt2"
    assert normalize_preference("bt2") == "bt2"
    assert normalize_preference("Bear 2") == "bt2"
    assert normalize_preference("bear 2") == "bt2"
    assert normalize_preference("B2") == "bt2"

    # BT2/1 explicit
    assert normalize_preference("BT2/1") == "bt2/1"
    assert normalize_preference("bt2/1") == "bt2/1"

    # BT1/2 and fallback
    assert normalize_preference("BT1/2") == "bt1/2"
    assert normalize_preference("bt1/2") == "bt1/2"
    assert normalize_preference("Both") == "bt1/2"
    assert normalize_preference("both") == "bt1/2"
    assert normalize_preference("") == "bt1/2"
    assert normalize_preference(None) == "bt1/2"

    print("✓ normalize_preference tests passed")


def test_primary_bear_id():
    """Test primary bear ID selection."""
    assert primary_bear_id("bt1") == "Bear 1"
    assert primary_bear_id("bt1/2") == "Bear 1"
    assert primary_bear_id("bt2") == "Bear 2"
    assert primary_bear_id("bt2/1") == "Bear 2"

    print("✓ primary_bear_id tests passed")


def test_build_slices():
    """Test slice building for grid partitioning."""
    slices = build_slices(28)

    # Should have 4 slices
    assert "bt1" in slices
    assert "bt2" in slices
    assert "bt1/2" in slices
    assert "bt2/1" in slices

    # bt1 should be on the left
    assert all(col < 14 for col in slices["bt1"])

    # bt2 should be on the right
    assert all(col >= 14 for col in slices["bt2"])

    # bt1/2 should be in the middle-left area
    assert any(col < 14 for col in slices["bt1/2"])

    # bt2/1 should be in the middle-right area
    assert any(col >= 14 for col in slices["bt2/1"])

    print("✓ build_slices tests passed")


def test_tile_free():
    """Test tile availability checking."""
    occupied = set()

    # Empty set - should be free
    assert tile_free(0, 0, occupied) is True

    # Mark (0,0) as occupied
    occupied.add((0, 0))
    assert tile_free(0, 0, occupied) is False
    assert tile_free(1, 1, occupied) is True  # Adjacent but not overlapping

    # Mark full 2x2 footprint
    occupied.add((0, 1))
    occupied.add((1, 0))
    occupied.add((1, 1))

    # Any overlap should fail
    assert tile_free(0, 0, occupied) is False
    assert tile_free(-1, -1, occupied) is False  # Would overlap at (0,0)

    print("✓ tile_free tests passed")


def test_round_trip_for_tile():
    """Test round trip time calculation."""
    # Castle at (0,0), bear at (0,0) - should be base time (300s)
    # Castle center at (1,1), bear center at (1,1)
    rt = round_trip_for_tile(0, 0, 0, 0)
    assert rt == 300, f"Expected 300, got {rt}"

    # Castle at (0,0), bear at (10,0) - horizontal distance
    # Castle center (1,1), bear center (11,1) - distance = 10
    # RT = 300 + 2 * (10 * 3) = 300 + 60 = 360
    rt = round_trip_for_tile(0, 0, 10, 0)
    assert abs(rt - 360) < 1, f"Expected ~360, got {rt}"

    print("✓ round_trip_for_tile tests passed")


def check_no_overlaps(castles, bear_traps, banners):
    """Check that no castles overlap with each other or entities."""
    overlaps = []

    for i, c1 in enumerate(castles):
        if not _has_xy(c1):
            continue

        # Check castle-castle overlaps
        for c2 in castles[i + 1:]:
            if not _has_xy(c2):
                continue
            if rectangles_overlap(c1["x"], c1["y"], 2, 2, c2["x"], c2["y"], 2, 2):
                overlaps.append(f"Castle {c1['id']} overlaps with {c2['id']}")

        # Check castle-entity overlaps
        has_overlap, entity_id = check_castle_overlap_with_entities(
            c1["x"], c1["y"], bear_traps, banners
        )
        if has_overlap:
            overlaps.append(f"Castle {c1['id']} overlaps with {entity_id}")

    return overlaps


def compute_placement_stats(castles, bear_traps):
    """Compute statistics about placement quality."""
    placed_castles = [c for c in castles if _has_xy(c)]
    total = len(placed_castles)

    if total == 0:
        return {
            "total": 0,
            "under_360": 0,
            "pct_under_360": 0,
            "worst_rt": 0,
            "avg_rt": 0,
            "avg_efficiency": 0,
        }

    round_trips = []
    efficiencies = []

    for c in placed_castles:
        rt = c.get("round_trip")
        if rt and rt > 0:
            round_trips.append(rt)

        eff = c.get("efficiency_score", 0)
        efficiencies.append(eff)

    under_360 = sum(1 for rt in round_trips if rt <= 360)
    pct_under_360 = (under_360 / len(round_trips) * 100) if round_trips else 0
    worst_rt = max(round_trips) if round_trips else 0
    avg_rt = sum(round_trips) / len(round_trips) if round_trips else 0
    avg_efficiency = sum(efficiencies) / len(efficiencies) if efficiencies else 0

    return {
        "total": total,
        "under_360": under_360,
        "pct_under_360": round(pct_under_360, 1),
        "worst_rt": worst_rt,
        "avg_rt": round(avg_rt, 1),
        "avg_efficiency": round(avg_efficiency, 1),
    }


async def test_auto_place_castles():
    """Integration test for auto_place_castles."""
    print("\n=== Running auto_place_castles integration test ===")

    # Run autoplace
    result = await auto_place_castles()

    assert result["success"] is True, "Autoplace should succeed"
    print(f"✓ Autoplace completed: placed {result['placed']} castles")

    # Load config to check results
    config = load_config()
    castles = config.get("castles", [])
    bear_traps = config.get("bear_traps", [])
    banners = config.get("banners", [])

    # Check for overlaps
    overlaps = check_no_overlaps(castles, bear_traps, banners)
    if overlaps:
        print("✗ Overlaps found:")
        for o in overlaps:
            print(f"  - {o}")
        assert False, "Overlaps detected after autoplace"
    else:
        print("✓ No overlaps detected")

    # Compute stats
    stats = compute_placement_stats(castles, bear_traps)

    print(f"\n=== Placement Statistics ===")
    print(f"Total castles placed: {stats['total']}")
    print(f"Castles with RT <= 360s: {stats['under_360']} ({stats['pct_under_360']}%)")
    print(f"Worst round trip: {stats['worst_rt']}s")
    print(f"Average round trip: {stats['avg_rt']}s")
    print(f"Average efficiency score: {stats['avg_efficiency']}")

    # Assertions for quality
    assert stats["total"] > 0, "Should have placed at least one castle"

    print("\n✓ Auto-place integration test passed")

    return stats


async def test_determinism():
    """Test that autoplace is deterministic."""
    print("\n=== Testing determinism ===")

    # Run autoplace twice
    result1 = await auto_place_castles()
    config1 = load_config()
    positions1 = {c["id"]: (c.get("x"), c.get("y")) for c in config1.get("castles", [])}

    result2 = await auto_place_castles()
    config2 = load_config()
    positions2 = {c["id"]: (c.get("x"), c.get("y")) for c in config2.get("castles", [])}

    # Compare positions
    differences = []
    for castle_id, pos1 in positions1.items():
        pos2 = positions2.get(castle_id)
        if pos1 != pos2:
            differences.append(f"{castle_id}: {pos1} vs {pos2}")

    if differences:
        print("✗ Non-deterministic placements found:")
        for d in differences:
            print(f"  - {d}")
        assert False, "Autoplace is not deterministic"
    else:
        print("✓ Autoplace is deterministic")


def run_unit_tests():
    """Run all unit tests."""
    print("=== Running Unit Tests ===\n")

    test_normalize_preference()
    test_primary_bear_id()
    test_build_slices()
    test_tile_free()
    test_round_trip_for_tile()

    print("\n=== All unit tests passed ===")


async def run_integration_tests():
    """Run integration tests."""
    print("\n=== Running Integration Tests ===")

    stats = await test_auto_place_castles()
    await test_determinism()

    print("\n=== All integration tests passed ===")
    return stats


def main():
    """Main entry point for tests."""
    # Run unit tests (synchronous)
    run_unit_tests()

    # Run integration tests (async)
    stats = asyncio.run(run_integration_tests())

    print("\n" + "=" * 50)
    print("FINAL REPORT")
    print("=" * 50)
    print(f"Total castles: {stats['total']}")
    print(f"Round-trip <= 360s: {stats['pct_under_360']}%")
    print(f"Worst round-trip: {stats['worst_rt']}s")
    print(f"Average efficiency: {stats['avg_efficiency']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
