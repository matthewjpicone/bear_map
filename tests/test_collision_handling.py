"""
Tests for collision handling in autoplace.

Run with: python tests/test_collision_handling.py
Or with pytest: python -m pytest tests/test_collision_handling.py -v
"""

try:
    import pytest

    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

    # Mock pytest decorators for standalone running
    class pytest:
        class mark:
            @staticmethod
            def asyncio(func):
                return func


from logic.placement import (
    is_tile_legal,
    find_nearest_legal_tile,
    auto_place_castles,
)
from logic.config import load_config, save_config


class TestIsTileLegal:
    """Test the is_tile_legal function."""

    def test_basic_legal_placement(self):
        """Test a basic legal placement with no obstacles."""
        occupied = set()
        bear_traps = []
        banners = []
        grid_size = 28

        # Position (10, 10) should be legal
        assert is_tile_legal(10, 10, grid_size, occupied, bear_traps, banners) is True

    def test_out_of_bounds(self):
        """Test that out-of-bounds positions are illegal."""
        occupied = set()
        bear_traps = []
        banners = []
        grid_size = 28

        # Top-left corner at (27, 27) would place 2x2 castle out of bounds
        assert is_tile_legal(27, 27, grid_size, occupied, bear_traps, banners) is False
        assert is_tile_legal(-1, 10, grid_size, occupied, bear_traps, banners) is False
        assert is_tile_legal(10, -1, grid_size, occupied, bear_traps, banners) is False

    def test_occupied_tile_collision(self):
        """Test that occupied tiles are detected."""
        occupied = {(10, 10), (10, 11), (11, 10), (11, 11)}
        bear_traps = []
        banners = []
        grid_size = 28

        # Any part of the 2x2 castle overlapping occupied tiles should be illegal
        assert is_tile_legal(10, 10, grid_size, occupied, bear_traps, banners) is False
        assert is_tile_legal(9, 9, grid_size, occupied, bear_traps, banners) is False
        assert is_tile_legal(11, 11, grid_size, occupied, bear_traps, banners) is False

        # Adjacent should be legal
        assert is_tile_legal(12, 10, grid_size, occupied, bear_traps, banners) is True
        assert is_tile_legal(8, 10, grid_size, occupied, bear_traps, banners) is True

    def test_bear_trap_exclusion_zone(self):
        """Test that bear trap 3x3 exclusion zones are respected."""
        occupied = set()
        bear_traps = [{"id": "Bear 1", "x": 10, "y": 10}]
        banners = []
        grid_size = 28

        # Bear at (10, 10) has 3x3 exclusion zone from (9, 9) to (11, 11)
        # 2x2 castle at (9, 9) would overlap
        assert is_tile_legal(9, 9, grid_size, occupied, bear_traps, banners) is False
        assert is_tile_legal(10, 10, grid_size, occupied, bear_traps, banners) is False
        assert is_tile_legal(11, 11, grid_size, occupied, bear_traps, banners) is False

        # Castle at (8, 8) would have tiles at (8,8), (9,8), (8,9), (9,9)
        # Tile (9,9) overlaps with bear exclusion zone
        assert is_tile_legal(8, 8, grid_size, occupied, bear_traps, banners) is False

        # Castle at (7, 10) should be legal (no overlap with bear zone)
        assert is_tile_legal(7, 10, grid_size, occupied, bear_traps, banners) is True

    def test_banner_collision(self):
        """Test that banner positions are respected."""
        occupied = set()
        bear_traps = []
        banners = [{"id": "B1", "x": 10, "y": 10}]
        grid_size = 28

        # Banner at (10, 10) blocks that single tile
        # 2x2 castle at (10, 10) would cover (10,10), (11,10), (10,11), (11,11)
        assert is_tile_legal(10, 10, grid_size, occupied, bear_traps, banners) is False

        # Castle at (9, 9) covers (9,9), (10,9), (9,10), (10,10) - overlaps banner
        assert is_tile_legal(9, 9, grid_size, occupied, bear_traps, banners) is False

        # Castle at (8, 10) covers (8,10), (9,10), (8,11), (9,11) - no overlap
        assert is_tile_legal(8, 10, grid_size, occupied, bear_traps, banners) is True

    def test_multiple_constraints(self):
        """Test with multiple bears, banners, and occupied tiles."""
        occupied = {(5, 5), (5, 6), (6, 5), (6, 6)}
        bear_traps = [
            {"id": "Bear 1", "x": 10, "y": 10},
            {"id": "Bear 2", "x": 20, "y": 20},
        ]
        banners = [{"id": "B1", "x": 15, "y": 15}]
        grid_size = 28

        # Check various positions
        assert (
            is_tile_legal(5, 5, grid_size, occupied, bear_traps, banners) is False
        )  # Occupied
        assert (
            is_tile_legal(10, 10, grid_size, occupied, bear_traps, banners) is False
        )  # Bear 1
        assert (
            is_tile_legal(20, 20, grid_size, occupied, bear_traps, banners) is False
        )  # Bear 2
        assert (
            is_tile_legal(15, 15, grid_size, occupied, bear_traps, banners) is False
        )  # Banner
        assert (
            is_tile_legal(0, 0, grid_size, occupied, bear_traps, banners) is True
        )  # Clear


class TestFindNearestLegalTile:
    """Test the find_nearest_legal_tile function."""

    def test_target_is_legal(self):
        """Test that if target is legal, it is returned."""
        occupied = set()
        bear_traps = []
        banners = []
        grid_size = 28

        result = find_nearest_legal_tile(
            10, 10, grid_size, occupied, bear_traps, banners
        )
        assert result == (10, 10)

    def test_finds_nearest_tile(self):
        """Test that nearest legal tile is found."""
        # Block the target position
        occupied = {(10, 10), (10, 11), (11, 10), (11, 11)}
        bear_traps = []
        banners = []
        grid_size = 28

        result = find_nearest_legal_tile(
            10, 10, grid_size, occupied, bear_traps, banners, max_distance=5
        )

        # Should find a tile at distance 2 (since distance 1 would overlap occupied)
        assert result is not None
        assert result != (10, 10)
        # Verify it's legal
        assert is_tile_legal(
            result[0], result[1], grid_size, occupied, bear_traps, banners
        )

    def test_no_legal_tile_found(self):
        """Test when no legal tile is found within max_distance."""
        # Create a fully occupied area
        occupied = set()
        for x in range(28):
            for y in range(28):
                occupied.add((x, y))
        bear_traps = []
        banners = []
        grid_size = 28

        result = find_nearest_legal_tile(
            10, 10, grid_size, occupied, bear_traps, banners, max_distance=5
        )
        assert result is None

    def test_deterministic_selection(self):
        """Test that the same input always produces the same output."""
        occupied = {(10, 10), (10, 11), (11, 10), (11, 11)}
        bear_traps = []
        banners = []
        grid_size = 28

        # Run multiple times
        result1 = find_nearest_legal_tile(
            10, 10, grid_size, occupied, bear_traps, banners, max_distance=5
        )
        result2 = find_nearest_legal_tile(
            10, 10, grid_size, occupied, bear_traps, banners, max_distance=5
        )
        result3 = find_nearest_legal_tile(
            10, 10, grid_size, occupied, bear_traps, banners, max_distance=5
        )

        assert result1 == result2 == result3


class TestAutoPlaceCollisions:
    """Test collision handling in auto_place_castles."""

    @pytest.mark.asyncio
    async def test_no_overlaps_after_autoplace(self):
        """Test that autoplace produces no overlaps."""
        # Set up a test configuration
        config = {
            "grid_size": 28,
            "banners": [{"id": "B1", "x": 14, "y": 14, "locked": True}],
            "bear_traps": [
                {"id": "Bear 1", "x": 8, "y": 15, "locked": True},
                {"id": "Bear 2", "x": 19, "y": 15, "locked": True},
            ],
            "castles": [
                {
                    "id": "C1",
                    "power": 1000000,
                    "player_level": 10,
                    "command_centre_level": 5,
                    "attendance": 50,
                    "preference": "Both",
                    "locked": False,
                    "x": None,
                    "y": None,
                },
                {
                    "id": "C2",
                    "power": 2000000,
                    "player_level": 15,
                    "command_centre_level": 10,
                    "attendance": 75,
                    "preference": "Bear 1",
                    "locked": False,
                    "x": None,
                    "y": None,
                },
                {
                    "id": "C3",
                    "power": 1500000,
                    "player_level": 12,
                    "command_centre_level": 8,
                    "attendance": 60,
                    "preference": "Bear 2",
                    "locked": False,
                    "x": None,
                    "y": None,
                },
            ],
        }

        save_config(config)
        await auto_place_castles()

        # Load updated config
        updated_config = load_config()
        castles = updated_config["castles"]
        bear_traps = updated_config["bear_traps"]
        banners = updated_config["banners"]

        # Check no castle-castle overlaps
        for i, c1 in enumerate(castles):
            if c1.get("x") is None or c1.get("y") is None:
                continue
            for j, c2 in enumerate(castles):
                if i >= j:
                    continue
                if c2.get("x") is None or c2.get("y") is None:
                    continue
                # Check if 2x2 rectangles overlap
                overlap = not (
                    c1["x"] + 2 <= c2["x"]
                    or c2["x"] + 2 <= c1["x"]
                    or c1["y"] + 2 <= c2["y"]
                    or c2["y"] + 2 <= c1["y"]
                )
                assert not overlap, f"Castles {c1['id']} and {c2['id']} overlap"

        # Check no castle-bear overlaps
        for castle in castles:
            if castle.get("x") is None or castle.get("y") is None:
                continue
            for bear in bear_traps:
                if bear.get("x") is None or bear.get("y") is None:
                    continue
                # Castle is 2x2 at (x, y), bear is 3x3 from (bx-1, by-1) to (bx+1, by+1)
                overlap = not (
                    castle["x"] + 2 <= bear["x"] - 1
                    or bear["x"] + 2 <= castle["x"]
                    or castle["y"] + 2 <= bear["y"] - 1
                    or bear["y"] + 2 <= castle["y"]
                )
                assert (
                    not overlap
                ), f"Castle {castle['id']} overlaps with bear {bear['id']}"

        # Check no castle-banner overlaps
        for castle in castles:
            if castle.get("x") is None or castle.get("y") is None:
                continue
            for banner in banners:
                if banner.get("x") is None or banner.get("y") is None:
                    continue
                # Castle is 2x2, banner is 1x1
                overlap = not (
                    castle["x"] + 2 <= banner["x"]
                    or banner["x"] + 1 <= castle["x"]
                    or castle["y"] + 2 <= banner["y"]
                    or banner["y"] + 1 <= castle["y"]
                )
                assert (
                    not overlap
                ), f"Castle {castle['id']} overlaps with banner {banner['id']}"

    @pytest.mark.asyncio
    async def test_deterministic_autoplace(self):
        """Test that autoplace produces deterministic results."""
        # Set up initial config
        config = {
            "grid_size": 28,
            "banners": [{"id": "B1", "x": 14, "y": 14, "locked": True}],
            "bear_traps": [
                {"id": "Bear 1", "x": 8, "y": 15, "locked": True},
                {"id": "Bear 2", "x": 19, "y": 15, "locked": True},
            ],
            "castles": [
                {
                    "id": "C1",
                    "power": 1000000,
                    "player_level": 10,
                    "command_centre_level": 5,
                    "attendance": 50,
                    "preference": "Both",
                    "locked": False,
                    "x": None,
                    "y": None,
                },
                {
                    "id": "C2",
                    "power": 2000000,
                    "player_level": 15,
                    "command_centre_level": 10,
                    "attendance": 75,
                    "preference": "Bear 1",
                    "locked": False,
                    "x": None,
                    "y": None,
                },
            ],
        }

        # Run autoplace twice
        save_config(config)
        await auto_place_castles()
        result1 = load_config()

        save_config(config)
        await auto_place_castles()
        result2 = load_config()

        # Compare castle positions
        castles1 = {c["id"]: (c.get("x"), c.get("y")) for c in result1["castles"]}
        castles2 = {c["id"]: (c.get("x"), c.get("y")) for c in result2["castles"]}

        assert castles1 == castles2, "Autoplace should produce deterministic results"

    @pytest.mark.asyncio
    async def test_staging_when_no_space(self):
        """Test that castles are staged (x=None, y=None) when no legal position exists."""
        # Create a very constrained scenario
        config = {
            "grid_size": 10,
            "banners": [],
            "bear_traps": [
                {"id": "Bear 1", "x": 3, "y": 3, "locked": True},
                {"id": "Bear 2", "x": 6, "y": 6, "locked": True},
            ],
            "castles": [],
        }

        # Add many castles to fill the available space
        for i in range(20):
            config["castles"].append(
                {
                    "id": f"C{i}",
                    "power": 1000000 + i * 100000,
                    "player_level": 10 + i,
                    "command_centre_level": 5 + i,
                    "attendance": 50 + i,
                    "preference": "Both",
                    "locked": False,
                    "x": None,
                    "y": None,
                }
            )

        save_config(config)
        await auto_place_castles()
        result = load_config()

        # Some castles should be staged (not placed)
        staged_castles = [
            c for c in result["castles"] if c.get("x") is None or c.get("y") is None
        ]
        placed_castles = [
            c
            for c in result["castles"]
            if c.get("x") is not None and c.get("y") is not None
        ]

        # Should have some staged castles due to space constraints
        assert (
            len(staged_castles) > 0
        ), "Some castles should be staged when space is limited"

        # All placed castles should have valid positions
        for castle in placed_castles:
            assert 0 <= castle["x"] <= config["grid_size"] - 2
            assert 0 <= castle["y"] <= config["grid_size"] - 2


if __name__ == "__main__":
    import asyncio

    # Run async tests
    async def run_tests():
        test = TestAutoPlaceCollisions()
        await test.test_no_overlaps_after_autoplace()
        print("✓ test_no_overlaps_after_autoplace passed")

        await test.test_deterministic_autoplace()
        print("✓ test_deterministic_autoplace passed")

        await test.test_staging_when_no_space()
        print("✓ test_staging_when_no_space passed")

    # Run sync tests
    test_legal = TestIsTileLegal()
    test_legal.test_basic_legal_placement()
    print("✓ test_basic_legal_placement passed")

    test_legal.test_out_of_bounds()
    print("✓ test_out_of_bounds passed")

    test_legal.test_occupied_tile_collision()
    print("✓ test_occupied_tile_collision passed")

    test_legal.test_bear_trap_exclusion_zone()
    print("✓ test_bear_trap_exclusion_zone passed")

    test_legal.test_banner_collision()
    print("✓ test_banner_collision passed")

    test_legal.test_multiple_constraints()
    print("✓ test_multiple_constraints passed")

    test_nearest = TestFindNearestLegalTile()
    test_nearest.test_target_is_legal()
    print("✓ test_target_is_legal passed")

    test_nearest.test_finds_nearest_tile()
    print("✓ test_finds_nearest_tile passed")

    test_nearest.test_no_legal_tile_found()
    print("✓ test_no_legal_tile_found passed")

    test_nearest.test_deterministic_selection()
    print("✓ test_deterministic_selection passed")

    asyncio.run(run_tests())
    print("\n✅ All tests passed!")
