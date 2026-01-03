"""
Tests for admin configuration editor.

Run with: PYTHONPATH=/home/runner/work/bear_map/bear_map python tests/test_admin.py
"""

import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

# Import app after setting up paths
from main import app
from logic.config import CONFIG_PATH

client = TestClient(app)


def test_admin_page_loads():
    """Test that the admin page endpoint returns HTML."""
    response = client.get("/admin")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert b"Admin Configuration Editor" in response.content


def test_get_config_success():
    """Test GET /api/admin/config returns config content."""
    response = client.get("/api/admin/config")
    assert response.status_code == 200
    data = response.json()
    assert "content" in data

    # Verify it's valid JSON
    config_content = json.loads(data["content"])
    assert isinstance(config_content, dict)


def test_post_config_valid_json():
    """Test POST /api/admin/config with valid JSON."""
    # Create a minimal valid config
    valid_config = {
        "grid_size": 28,
        "castles": [],
        "bear_traps": [],
        "banners": [],
        "efficiency_scale": [],
    }

    config_str = json.dumps(valid_config, indent=2)

    # Mock the notify function to avoid WebSocket complications
    with patch("server.broadcast.notify_config_updated", new_callable=AsyncMock):
        response = client.post("/api/admin/config", json={"content": config_str})

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "successfully" in data["message"].lower()


def test_post_config_invalid_json():
    """Test POST /api/admin/config with invalid JSON."""
    invalid_json = '{"grid_size": 28, "castles": [}'  # Missing closing bracket

    response = client.post("/api/admin/config", json={"content": invalid_json})

    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "Invalid JSON" in data["detail"]


def test_post_config_empty_content():
    """Test POST /api/admin/config with empty content."""
    response = client.post("/api/admin/config", json={"content": ""})

    assert response.status_code == 400
    # Empty string is invalid JSON


def test_post_config_malformed_json():
    """Test POST /api/admin/config with malformed JSON."""
    malformed_cases = [
        "not json at all",
        "{key: 'value'}",  # Unquoted key
        "{'single': 'quotes'}",  # Single quotes instead of double
        "[1, 2, 3,]",  # Trailing comma
    ]

    for malformed in malformed_cases:
        response = client.post("/api/admin/config", json={"content": malformed})
        assert response.status_code == 400, f"Expected 400 for: {malformed}"


def test_get_config_preserves_format():
    """Test that GET returns the exact file content."""
    # Read the actual config file
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        expected_content = f.read()

    response = client.get("/api/admin/config")
    assert response.status_code == 200
    data = response.json()

    # The content should match exactly
    assert data["content"] == expected_content


def test_post_config_updates_file():
    """Test that POST actually updates the config file."""
    # Create a backup of the current config
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        original_config = f.read()

    try:
        # Create a test config
        test_config = {
            "grid_size": 99,
            "castles": [],
            "bear_traps": [],
            "banners": [],
            "efficiency_scale": [],
            "test_marker": "admin_test",
        }

        config_str = json.dumps(test_config, indent=2)

        # Update via API
        with patch("server.broadcast.notify_config_updated", new_callable=AsyncMock):
            response = client.post("/api/admin/config", json={"content": config_str})

        assert response.status_code == 200

        # Verify the file was actually updated
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            updated_content = json.load(f)

        assert updated_content["test_marker"] == "admin_test"
        assert updated_content["grid_size"] == 99

    finally:
        # Restore original config
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(original_config)


def test_post_config_with_special_characters():
    """Test POST with special characters and unicode."""
    special_config = {
        "grid_size": 28,
        "castles": [
            {
                "id": "Castle 1",
                "player": "Player™ 🐻",
                "unicode_test": "日本語",
            }
        ],
        "bear_traps": [],
        "banners": [],
        "efficiency_scale": [],
    }

    config_str = json.dumps(special_config, indent=2, ensure_ascii=False)

    # Create a backup
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        original_config = f.read()

    try:
        with patch("server.broadcast.notify_config_updated", new_callable=AsyncMock):
            response = client.post("/api/admin/config", json={"content": config_str})

        assert response.status_code == 200

        # Verify special characters were preserved
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            updated = json.load(f)

        assert updated["castles"][0]["player"] == "Player™ 🐻"
        assert updated["castles"][0]["unicode_test"] == "日本語"

    finally:
        # Restore
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(original_config)


if __name__ == "__main__":
    print("Running admin tests...")

    test_admin_page_loads()
    print("✓ test_admin_page_loads")

    test_get_config_success()
    print("✓ test_get_config_success")

    test_post_config_valid_json()
    print("✓ test_post_config_valid_json")

    test_post_config_invalid_json()
    print("✓ test_post_config_invalid_json")

    test_post_config_empty_content()
    print("✓ test_post_config_empty_content")

    test_post_config_malformed_json()
    print("✓ test_post_config_malformed_json")

    test_get_config_preserves_format()
    print("✓ test_get_config_preserves_format")

    test_post_config_updates_file()
    print("✓ test_post_config_updates_file")

    test_post_config_with_special_characters()
    print("✓ test_post_config_with_special_characters")

    print("\nAll admin tests passed! ✨")
