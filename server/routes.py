"""
Basic API routes.

This module contains the fundamental API endpoints for serving the application
and retrieving basic data.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
"""

import csv
import json
import os
from datetime import datetime
from io import BytesIO, StringIO

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from PIL import Image, ImageDraw
from pydantic import BaseModel

from logic.config import load_config, save_config
from logic.scoring import compute_efficiency, compute_priority


class DiscordMapRequest(BaseModel):
    """Request model for sending map to Discord."""

    channel: str
    message: str


TILE_SIZE = 40


def parse_power(s: str) -> int:
    """Parse power string like '30.7M' to integer."""
    s = s.strip()
    multiplier = 1
    if s.endswith("M"):
        multiplier = 1000000
        s = s[:-1]
    elif s.endswith("K"):
        multiplier = 1000
        s = s[:-1]
    try:
        return int(float(s) * multiplier)
    except ValueError:
        return 0


def efficiency_color(value):
    """Get color for efficiency value."""
    if value is None or not isinstance(value, (int, float)):
        return "#374151"
    efficiency_scale = [
        {"max": 6, "color": "#16a34a"},
        {"max": 10, "color": "#2563eb"},
        {"max": 15, "color": "#64748b"},
        {"max": float("inf"), "color": "#1f2937"},
    ]
    for tier in efficiency_scale:
        if value <= tier["max"]:
            return tier["color"]
    return efficiency_scale[-1]["color"]


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
        "avg_round_trip": config.get("avg_round_trip"),
        "avg_rallies": config.get("avg_rallies"),
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
        "id",
        "player",
        "power",
        "player_level",
        "command_centre_level",
        "attendance",
        "rallies_30min",
        "preference",
        "current_trap",
        "recommended_trap",
        "priority",
        "efficiency",
        "round_trip",
        "last_updated",
        "x",
        "y",
        "locked",
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
            "preference": castle.get("preference", "BT1/2"),
            "current_trap": castle.get("current_trap", ""),
            "recommended_trap": castle.get("recommended_trap", ""),
            "priority": castle.get("priority_score"),
            "efficiency": castle.get("efficiency_score"),
            "round_trip": castle.get("round_trip"),
            "last_updated": castle.get("last_updated", ""),
            "x": castle.get("x"),
            "y": castle.get("y"),
            "locked": castle.get("locked", False),
        }
        writer.writerow(row)

    output.seek(0)

    def iter_csv():
        yield output.getvalue()

    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=castles.csv"},
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
    lines = text.split("\n")
    if not lines or lines[0].strip() != "name,power,level":
        # Assume it's raw text, try to parse as comma-separated
        # But for now, assume it's the format
        pass

    parsed_data = []
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 3:
            continue
        name, power_str, level_str = parts
        try:
            power = parse_power(power_str)
            level = int(level_str)
            parsed_data.append(
                {
                    "player": name,
                    "power": power,
                    "player_level": level,
                }
            )
        except ValueError:
            continue  # Skip invalid lines

    if not parsed_data:
        return {"success": False, "message": "No valid data found in file"}

    config = load_config()
    existing_castles = config.get("castles", [])
    existing_by_player = {
        c.get("player", ""): c for c in existing_castles if c.get("player")
    }

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
                "preference": "BT1/2",  # default
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

    return {
        "success": True,
        "message": f"Updated {updated_count} castles, added {added_count} new castles",
    }


class CastleCreate(BaseModel):
    """Request model for creating a new castle."""

    player: str
    power: int = 0
    player_level: int = 0
    command_centre_level: int = 0
    attendance: int | None = None
    rallies_30min: int = 0
    preference: str = "BT1/2"
    x: int = 0
    y: int = 0


@router.post("/api/castles")
async def create_castle(castle_data: CastleCreate):
    """Create a new castle.

    Args:
        castle_data: Castle information.

    Returns:
        The newly created castle with assigned ID.
    """
    config = load_config()
    castles = config.get("castles", [])

    # Generate new castle ID
    castle_id = f"Castle {len(castles) + 1}"

    now = datetime.now().isoformat()

    # Determine attendance value
    attendance_value = castle_data.attendance
    if attendance_value is None:
        # Calculate average of existing non-null attendance values
        existing_attendance = [
            c.get("attendance") for c in castles if c.get("attendance") is not None
        ]
        if existing_attendance:
            attendance_value = round(
                sum(existing_attendance) / len(existing_attendance)
            )
        else:
            attendance_value = 0

    new_castle = {
        "id": castle_id,
        "player": castle_data.player,
        "power": castle_data.power,
        "player_level": castle_data.player_level,
        "command_centre_level": castle_data.command_centre_level,
        "attendance": attendance_value,
        "rallies_30min": castle_data.rallies_30min,
        "preference": castle_data.preference,
        "current_trap": "",
        "recommended_trap": "",
        "priority_score": 0.0,
        "efficiency_score": 0.0,
        "round_trip": None,
        "last_updated": now,
        "x": castle_data.x,
        "y": castle_data.y,
        "locked": False,
    }

    castles.append(new_castle)
    config["castles"] = castles

    # Recompute priorities and efficiencies
    compute_priority(castles)
    compute_efficiency(config, castles)

    save_config(config)

    # Notify clients
    from server.broadcast import notify_config_updated

    await notify_config_updated()

    return {"success": True, "castle": new_castle}


@router.get("/api/download_map_image")
def download_map_image():
    """Download the current map as a PNG image.

    Renders the map using a headless browser to ensure exact client-side
    rendering is captured server-side.

    Returns:
        PNG image file.
    """
    try:
        from server.screenshot import get_map_screenshot_sync

        # Render using headless browser (app runs on port 3000)
        buf = get_map_screenshot_sync(base_url="http://localhost:3000")

        return StreamingResponse(
            buf,
            media_type="image/png",
            headers={"Content-Disposition": "attachment; filename=map.png"},
        )

    except Exception as e:
        print(f"Error generating image: {e}")
        import traceback

        traceback.print_exc()

        # Return error image
        error_img = Image.new("RGB", (1600, 1600), (255, 0, 0))
        draw = ImageDraw.Draw(error_img)
        draw.text((10, 10), f"Error: {str(e)[:80]}", fill=(255, 255, 255))
        buf = BytesIO()
        error_img.save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="image/png",
            headers={"Content-Disposition": "attachment; filename=error.png"},
        )


@router.post("/api/send_map_to_discord")
def send_map_to_discord(request_data: DiscordMapRequest):
    """Send the current map image to a Discord webhook channel.

    Args:
        request_data: DiscordMapRequest with 'channel' and 'message'.
                     channel: 'r4' or 'announcements'
                     message: Custom message to include with the image

    Returns:
        Success/error response.
    """
    try:
        import requests

        from server.screenshot import get_map_screenshot_sync

        channel = request_data.channel
        message = request_data.message

        # Discord webhook URLs
        webhooks = {
            "r4": "https://discord.com/api/webhooks/1451086715975503942/fsGgLPkDQCKYr5txMsFyggj-IelKqYdvUQdF2Xdc9S-u1PglG5YM-nIDRUlT9DT7R1HA",
            "announcements": "https://discord.com/api/webhooks/1451086879725326477/K4yQSWtl8xP3bHGRDPTgEwPaKhBFjpnK4lKqDcAwJvMC6QTtUT_xdrg4Wx-9YFlE5XN6",
            "general": "https://discord.com/api/webhooks/1451089385574371433/c5D8N0OSbO3c5pL1CAbifsuV6IVLKUkCmrCrqlNsJgMaAkGAchgcgtxu0Zg4GpxpMOC4",
        }

        # Get the map screenshot
        screenshot_buf = get_map_screenshot_sync(base_url="http://localhost:3000")

        # Determine which channels to post to
        channels_to_post = []
        if channel == "announcements":
            # Post to both Announcements and General
            channels_to_post = ["announcements", "general"]
        else:
            channels_to_post = [channel]

        # Send to each channel
        failed_channels = []
        for target_channel in channels_to_post:
            webhook_url = webhooks.get(target_channel)
            if not webhook_url:
                failed_channels.append(target_channel)
                continue

            # Reset buffer position for each send
            screenshot_buf.seek(0)

            # Send to Discord
            files = {"file": ("map.png", screenshot_buf.getvalue(), "image/png")}
            data = {"content": message}

            response = requests.post(webhook_url, files=files, data=data)

            if response.status_code not in (200, 204):
                failed_channels.append(target_channel)

        if failed_channels:
            return {
                "success": False,
                "error": f"Failed to send to: {', '.join(failed_channels)}",
            }

        return {
            "success": True,
            "message": f"Map sent to {', '.join(channels_to_post)} channel(s)",
        }

    except Exception as e:
        print(f"Error sending map to Discord: {e}")
        import traceback

        traceback.print_exc()
        return {"success": False, "error": str(e)}
