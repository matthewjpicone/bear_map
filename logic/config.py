"""
Configuration management module.

This module provides utilities for loading, saving, and managing the application
configuration stored in config.json.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
"""

import json
import os
from typing import Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json.

    Returns:
        Configuration dictionary.
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: Dict[str, Any]):
    """Save configuration to config.json.

    Args:
        config: Configuration dictionary to save.
    """
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
