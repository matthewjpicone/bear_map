"""
Basic API routes.

This module contains the fundamental API endpoints for serving the application
and retrieving basic data.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
"""

import json
import os
import csv
from io import StringIO
from typing import Dict, Any
from datetime import datetime

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse

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
        "map_score_900": config.get("map_score_900"),
        "map_score_percent": config.get("map_score_percent"),
        "empty_score_100": config.get("empty_score_100"),
        "efficiency_avg": config.get("efficiency_avg"),
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


@router.get("/api/download_csv")
def download_csv():
    """Download all castle data as CSV.

    Returns:
        CSV file with all castle information.
    """
    config = load_config()
    castles = config.get("castles", [])

    output = StringIO()
    fieldnames = [
        "id", "player", "power", "player_level", "command_centre_level",
        "attendance", "rallies_30min", "preference", "current_trap", "recommended_trap",
        "priority", "efficiency", "round_trip", "last_updated", "x", "y", "locked"
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for castle in castles:
        row = {
            "id": castle.get("id", ""),
            "player": castle.get("player", ""),
            "power": castle.get("power", 0),
            "player_level": castle.get("player_level", 0),
            "command_centre_level": castle.get("command_centre_level", 0),
            "attendance": castle.get("attendance"),
            "rallies_30min": castle.get("rallies_30min", 0),
            "preference": castle.get("preference", "Both"),
            "current_trap": castle.get("current_trap", ""),
            "recommended_trap": castle.get("recommended_trap", ""),
            "priority": castle.get("priority_score"),
            "efficiency": castle.get("efficiency_score"),
            "round_trip": castle.get("round_trip"),
            "last_updated": castle.get("last_updated", ""),
            "x": castle.get("x"),
            "y": castle.get("y"),
            "locked": castle.get("locked", False)
        }
        writer.writerow(row)

    output.seek(0)

    def iter_csv():
        yield output.getvalue()

    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=castles.csv"}
    )


@router.post("/api/upload_csv")
async def upload_csv(file: UploadFile = File(...)):
    """Upload castle data from CSV file.

    Replaces the current castle data with the uploaded CSV.

    Args:
        file: CSV file containing castle data.

    Returns:
        Success message with number of castles uploaded.
    """
    content = await file.read()
    text = content.decode("utf-8")

    reader = csv.DictReader(StringIO(text))
    castles = []
    now = datetime.now().isoformat()
    for row in reader:
        castle = {
            "id": row.get("id", ""),
            "player": row.get("player", ""),
            "power": int(row["power"]) if row.get("power") and row["power"].isdigit() else 0,
            "player_level": int(row["player_level"]) if row.get("player_level") and row["player_level"].isdigit() else 0,
            "command_centre_level": int(row["command_centre_level"]) if row.get("command_centre_level") and row["command_centre_level"].isdigit() else 0,
            "attendance": int(row["attendance"]) if row.get("attendance") and row["attendance"].isdigit() else None,
            "rallies_30min": int(row["rallies_30min"]) if row.get("rallies_30min") and row["rallies_30min"].isdigit() else 0,
            "preference": row.get("preference", "Both"),
            "current_trap": row.get("current_trap", ""),
            "recommended_trap": row.get("recommended_trap", ""),
            "priority_score": float(row["priority"]) if row.get("priority") and row["priority"].replace('.', '').isdigit() else 0.0,
            "efficiency_score": float(row["efficiency"]) if row.get("efficiency") and row["efficiency"].replace('.', '').isdigit() else 0.0,
            "round_trip": int(row["round_trip"]) if row.get("round_trip") and row["round_trip"].isdigit() else None,
            "last_updated": now,  # Update to current time
            "x": int(row["x"]) if row.get("x") and row["x"].isdigit() else None,
            "y": int(row["y"]) if row.get("y") and row["y"].isdigit() else None,
            "locked": str(row.get("locked", "False")).lower() in ("true", "1", "yes"),
        }
        castles.append(castle)

    config = load_config()
    config["castles"] = castles

    # Recompute priorities and efficiencies
    compute_priority(castles)
    compute_efficiency(config, castles)

    save_config(config)

    # Notify clients to refresh data
    from server.broadcast import notify_config_updated
    await notify_config_updated()

    return {"success": True, "message": f"Uploaded {len(castles)} castles"}
