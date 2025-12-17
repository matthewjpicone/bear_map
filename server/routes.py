"""
Basic API routes.

This module contains the fundamental API endpoints for serving the application
and retrieving basic data.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
"""

import json
import os
from typing import Dict, Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, FileResponse

from logic.config import load_config, save_config
from logic.scoring import compute_priority, compute_efficiency

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_PATH = os.path.join(BASE_DIR, "version.json")
DEFAULT_VERSION = "1.0.4"


@router.get("/", response_class=HTMLResponse)
def index():
    """Serve the main HTML page.

    Returns:
        HTML page from static/index.html.
    """
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))


@router.get("/api/map")
def get_map():
    """Get the current map configuration.

    Returns:
        Dictionary containing grid size, efficiency scale, and all entities
        (banners, bear traps, castles).
    """
    config = load_config()

    # Update round trip times for all castles
    from logic.placement import update_all_round_trip_times
    update_all_round_trip_times(config.get("castles", []), config.get("bear_traps", []))

    # Compute priority and efficiency
    castles = config.get("castles", [])
    compute_priority(castles)
    compute_efficiency(config, castles)

    # Save the updated config with calculated round trip times
    save_config(config)

    return {
        "grid_size": config["grid_size"],
        "efficiency_scale": config["efficiency_scale"],
        "banners": config.get("banners", []),
        "bear_traps": config.get("bear_traps", []),
        "castles": config.get("castles", []),
    }


@router.get("/api/version")
def get_version():
    """Get the application version.

    Returns:
        Dictionary with version string.
    """
    try:
        with open(VERSION_PATH, "r", encoding="utf-8") as f:
            version_data = json.load(f)
        return version_data
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return {"version": DEFAULT_VERSION}
