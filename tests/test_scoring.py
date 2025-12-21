"""
Tests for scoring module.

Run with: python -m pytest tests/test_scoring.py
"""

from logic.scoring import chebyshev_distance, compute_efficiency, compute_priority


def test_chebyshev_distance():
    assert chebyshev_distance(0, 0, 3, 4) == 4
    assert chebyshev_distance(0, 0, 1, 1) == 1
    assert chebyshev_distance(0, 0, 0, 0) == 0


def test_compute_priority():
    castles = [
        {
            "id": "C1",
            "power": 1000000,
            "player_level": 10,
            "command_centre_level": 5,
            "attendance": 50,
        },
        {
            "id": "C2",
            "power": 2000000,
            "player_level": 15,
            "command_centre_level": 10,
            "attendance": 75,
        },
    ]

    result = compute_priority(castles)

    # C2 should have higher priority_score
    assert result[0]["priority_score"] < result[1]["priority_score"]
    assert (
        result[0]["priority_rank_100"] > result[1]["priority_rank_100"]
    )  # Lower rank number is better

    # Check fields exist
    for c in result:
        assert "priority_score" in c
        assert "priority_rank_100" in c
        assert "priority_debug" in c


def test_compute_priority_null_attendance():
    castles = [
        {
            "id": "C1",
            "power": 1000000,
            "player_level": 10,
            "command_centre_level": 5,
            "attendance": None,
        }
    ]

    result = compute_priority(castles)

    # Should not crash, use median
    assert "priority_score" in result[0]


def test_compute_efficiency_simple():
    map_data = {
        "grid_size": 10,
        "banners": [],
        "bear_traps": [
            {"id": "Bear 1", "x": 0, "y": 0},
            {"id": "Bear 2", "x": 9, "y": 9},
        ],
    }

    castles = [
        {
            "id": "C1",
            "preference": "Bear 1",
            "x": 1,
            "y": 1,
            "priority_score": 0.8,
            "priority_rank_100": 10,
        },
        {
            "id": "C2",
            "preference": "Bear 1",
            "x": 2,
            "y": 2,
            "priority_score": 0.6,
            "priority_rank_100": 20,
        },
    ]

    result = compute_efficiency(map_data, castles)

    # Check fields exist
    for c in result:
        assert "efficiency_score" in c
        assert "actual_travel_time" in c
        assert "ideal_travel_time" in c
        assert "regret" in c

    # If placed optimally, scores should be low
    # But in this case, they are close, so scores should be reasonable


if __name__ == "__main__":
    test_chebyshev_distance()
    test_compute_priority()
    test_compute_priority_null_attendance()
    test_compute_efficiency_simple()
    print("All tests passed!")
