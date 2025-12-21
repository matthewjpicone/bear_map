"""
Configuration management module.

This module provides utilities for loading, saving, and managing the application
configuration stored in config.json.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
"""

import json
import os
from datetime import datetime
from typing import Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json.

    Returns:
        Configuration dictionary with all required fields ensured.
    """
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        config = get_default_config()

    # Ensure all required fields are present
    config = ensure_config_fields(config)
    return config


def save_config(config: Dict[str, Any]):
    """Save configuration to config.json.

    Args:
        config: Configuration dictionary to save.
    """
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_default_config() -> Dict[str, Any]:
    """Get default configuration structure.

    Returns:
        Default configuration dictionary.
    """
    return {
        "grid_size": 28,
        "castles": [],
        "bear_traps": [],
        "banners": [],
        "efficiency_scale": [
            {"max": 6, "color": "#16a34a", "label": "Excellent"},
            {"max": 10, "color": "#2563eb", "label": "Good"},
            {"max": 15, "color": "#64748b", "label": "Poor"},
            {"max": float('inf'), "color": "#1f2937", "label": "Bad"}
        ]
    }


def ensure_config_fields(config: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure all required fields are present in the configuration.

    Args:
        config: Configuration dictionary to update.

    Returns:
        Updated configuration dictionary.
    """
    # Ensure top-level structure
    config.setdefault("grid_size", 28)
    config.setdefault("castles", [])
    config.setdefault("bear_traps", [])
    config.setdefault("banners", [])

    # Migrate old "banner" field to "banners" if present
    if "banner" in config and not config.get("banners"):
        config["banners"] = config["banner"]
        del config["banner"]

    config.setdefault("efficiency_scale", [
        {"max": 6, "color": "#16a34a", "label": "Excellent"},
        {"max": 10, "color": "#2563eb", "label": "Good"},
        {"max": 15, "color": "#64748b", "label": "Poor"},
        {"max": float('inf'), "color": "#1f2937", "label": "Bad"}
    ])

    # Ensure each castle has all required fields
    for castle in config["castles"]:
        ensure_castle_fields(castle)

    for bear in config["bear_traps"]:
        ensure_bear_fields(bear)

    for banner in config["banners"]:
        ensure_banner_fields(banner)

    return config


def ensure_castle_fields(castle: Dict[str, Any]):
    """Ensure a castle has all required fields with appropriate defaults.

    Args:
        castle: Castle dictionary to update.
    """
    now = datetime.now().isoformat()

    defaults = {
        "id": "",
        "player": "",
        "power": 0,
        "player_level": 0,
        "command_centre_level": 0,
        "attendance": 0,
        "rallies_30min": 0,
        "preference": "BT1/2",
        "current_trap": "",
        "recommended_trap": "",
        "priority": 0.0,
        "efficiency": 0.0,
        "round_trip": "NA",
        "last_updated": now,  # Set to current time if missing
        "x": None,
        "y": None,
        "locked": False,
    }

    for key, default in defaults.items():
        castle.setdefault(key, default)


def ensure_bear_fields(bear: Dict[str, Any]):
    """Ensure a bear trap has all required fields with appropriate defaults.

    Args:
        bear: Bear trap dictionary to update.
    """
    defaults = {
        "id": "",
        "x": None,
        "y": None,
        "locked": False,
    }

    for key, default in defaults.items():
        bear.setdefault(key, default)


def ensure_banner_fields(banner: Dict[str, Any]):
    """Ensure a banner has all required fields with appropriate defaults.

    Args:
        banner: Banner dictionary to update.
    """
    defaults = {
        "id": "",
        "x": None,
        "y": None,
        "locked": False,
    }

    for key, default in defaults.items():
        banner.setdefault(key, default)
