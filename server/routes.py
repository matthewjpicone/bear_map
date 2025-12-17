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


def parse_power(s: str) -> int:
    """Parse power string like '30.7M' to integer."""
    s = s.strip()
    multiplier = 1
    if s.endswith('M'):
        multiplier = 1000000
        s = s[:-1]
    elif s.endswith('K'):
        multiplier = 1000
        s = s[:-1]
    try:
        return int(float(s) * multiplier)
    except ValueError:
        return 0


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
    """Upload castle data from CSV file or raw text.

    Merges with existing data: updates matching players, adds new ones.

    Args:
        file: File containing castle data (CSV or raw text).

    Returns:
        Success message with number of castles updated/added.
    """
    content = await file.read()
    text = content.decode("utf-8").strip()

    # Parse the data
    lines = text.split('\n')
    if not lines or lines[0].strip() != 'name,power,level':
        # Assume it's raw text, try to parse as comma-separated
        # But for now, assume it's the format
        pass

    parsed_data = []
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(',')]
        if len(parts) != 3:
            continue
        name, power_str, level_str = parts
        try:
            power = parse_power(power_str)
            level = int(level_str)
            parsed_data.append({
                "player": name,
                "power": power,
                "player_level": level,
            })
        except ValueError:
            continue  # Skip invalid lines

    if not parsed_data:
        return {"success": False, "message": "No valid data found in file"}

    config = load_config()
    existing_castles = config.get("castles", [])
    existing_by_player = {c.get("player", ""): c for c in existing_castles if c.get("player")}

    now = datetime.now().isoformat()
    updated_count = 0
    added_count = 0

    for data in parsed_data:
        player = data["player"]
        if player in existing_by_player:
            # Update existing
            existing_by_player[player].update(data)
            existing_by_player[player]["last_updated"] = now
            updated_count += 1
        else:
            # Add new
            castle = {
                "id": f"Castle {len(existing_castles) + added_count + 1}",
                "player": player,
                "power": data["power"],
                "player_level": data["player_level"],
                "command_centre_level": 0,  # default
                "attendance": None,  # default
                "rallies_30min": 0,
                "preference": "Both",  # default
                "current_trap": "",
                "recommended_trap": "",
                "priority_score": 0.0,
                "efficiency_score": 0.0,
                "round_trip": None,
                "last_updated": now,
                "x": None,
                "y": None,
                "locked": False,
            }
            existing_castles.append(castle)
            added_count += 1

    config["castles"] = existing_castles

    # Recompute priorities and efficiencies
    compute_priority(existing_castles)
    compute_efficiency(config, existing_castles)

    save_config(config)

    # Notify clients to refresh data
    from server.broadcast import notify_config_updated
    await notify_config_updated()

    return {"success": True, "message": f"Updated {updated_count} castles, added {added_count} new castles"}
