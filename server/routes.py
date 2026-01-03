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

# Constants for CSV upload
PLACEHOLDER_VALUES = {"none", "n/a", "na", "tbd", "tba", "-", ""}

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


def normalize_preference(value: str) -> str:
    """Normalize preference values to valid internal format.

    Args:
        value: Preference string from CSV (e.g., "both", "Bear 1", "BT1").

    Returns:
        Normalized preference value or default "BT1/2".
    """
    value = value.strip().lower()

    # Map common variations to internal values
    preference_mapping = {
        "bt1": "BT1",
        "bt2": "BT2",
        "bt1/2": "BT1/2",
        "bt2/1": "BT2/1",
        "bear 1": "BT1",
        "bear 2": "BT2",
        "both": "BT1/2",
        "either": "BT1/2",
    }

    normalized = preference_mapping.get(value)
    if normalized:
        return normalized

    # If it's already a valid preference (case-insensitive), return it
    from logic.validation import VALID_PREFERENCES

    for valid_pref in VALID_PREFERENCES:
        if value == valid_pref.lower():
            return valid_pref

    # Default fallback
    return "BT1/2"


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
    """Upload castle data from CSV file.

    Flexible CSV upload that matches by ID or player name and updates all provided fields.
    Supports various CSV formats - any columns matching castle field names will be updated.

    Args:
        file: CSV file containing castle data with headers.

    Returns:
        Success message with number of castles updated/added.
    """
    from logic.validation import (
        ALLOWED_CASTLE_FIELDS,
        VALID_PREFERENCES,
        sanitise_int,
        sanitise_player_name,
    )

    content = await file.read()
    text = content.decode("utf-8").strip()

    if not text:
        return {"success": False, "message": "Empty file"}

    # Parse CSV with headers
    try:
        csv_reader = csv.DictReader(StringIO(text))
        rows = list(csv_reader)
    except Exception as e:
        return {"success": False, "message": f"Failed to parse CSV: {str(e)}"}

    if not rows:
        return {"success": False, "message": "No data rows found in CSV"}

    # Map common variations of field names to internal field names
    field_mapping = {
        "id": "id",
        "castle_id": "id",
        "player_id": "id",
        "player": "player",
        "player_name": "player",
        "name": "player",
        "discord_username": "discord_username",
        "discord": "discord_username",
        "power": "power",
        "player_level": "player_level",
        "level": "player_level",
        "command_centre_level": "command_centre_level",
        "cc_level": "command_centre_level",
        "cc": "command_centre_level",
        "attendance": "attendance",
        "attendance_count": "attendance",
        "rallies_30min": "rallies_30min",
        "rallies": "rallies_30min",
        "preference": "preference",
        "pref": "preference",
        "trap_preference": "preference",
        "current_trap": "current_trap",
        "recommended_trap": "recommended_trap",
        "x": "x",
        "y": "y",
        "locked": "locked",
    }

    config = load_config()
    existing_castles = config.get("castles", [])

    # Build lookup maps for matching
    existing_by_id = {c.get("id"): c for c in existing_castles if c.get("id")}
    existing_by_player = {
        c.get("player", "").lower(): c for c in existing_castles if c.get("player")
    }

    now = datetime.now().isoformat()
    
    # Calculate the next available ID for new castles without an ID
    max_castle_num = 0
    for existing_id in existing_by_id.keys():
        if existing_id.startswith("Castle "):
            try:
                num = int(existing_id.split(" ")[1])
                max_castle_num = max(max_castle_num, num)
            except (ValueError, IndexError):
                pass
    next_castle_num = max_castle_num + 1
    updated_count = 0
    added_count = 0
    error_lines = []

    for row_idx, row in enumerate(rows, start=2):  # Start at 2 (header is row 1)
        # Normalize the row keys to lowercase for case-insensitive matching
        # Also filter out empty values and special placeholder values
        normalized_row = {}
        for k, v in row.items():
            if v:
                v_stripped = v.strip().lower()
                # Skip empty and placeholder values
                if v_stripped and v_stripped not in PLACEHOLDER_VALUES:
                    normalized_row[k.lower().strip()] = v.strip()

        if not normalized_row:
            continue

        # Extract and map fields from CSV
        parsed_data = {}
        csv_id = None
        csv_player = None

        for csv_field, value in normalized_row.items():
            internal_field = field_mapping.get(csv_field)
            if not internal_field:
                continue  # Skip unknown fields

            # Special handling for ID and player (used for matching)
            if internal_field == "id":
                csv_id = value
                parsed_data["id"] = value
            elif internal_field == "player":
                csv_player = value
                parsed_data["player"] = value
            else:
                parsed_data[internal_field] = value

        # If we have an ID but no player name, use ID as player name
        # This handles formats where player_id is actually the player name
        if csv_id and not csv_player:
            csv_player = csv_id
            parsed_data["player"] = csv_id

        # Try to match existing castle by ID first, then by player name
        # Note: Only match by player name if no ID was provided in CSV
        matched_castle = None
        if csv_id:
            if csv_id in existing_by_id:
                matched_castle = existing_by_id[csv_id]
            # If CSV has an ID but it doesn't exist, don't fall back to player matching
            # This prevents accidental updates to wrong castles
        elif csv_player:
            # Only match by player name if no ID was provided
            matched_castle = existing_by_player.get(csv_player.lower())

        if matched_castle:
            # Update existing castle
            any_fields_changed = False
            try:
                for field, value in parsed_data.items():
                    if field == "id":
                        continue  # Don't change ID

                    # Validate and sanitize based on field type
                    if field == "player":
                        matched_castle["player"] = sanitise_player_name(value)
                        any_fields_changed = True
                    elif field == "discord_username":
                        matched_castle["discord_username"] = sanitise_player_name(value)
                        any_fields_changed = True
                    elif field == "preference":
                        normalized_pref = normalize_preference(value)
                        matched_castle["preference"] = normalized_pref
                        any_fields_changed = True
                    elif field == "attendance":
                        matched_castle["attendance"] = sanitise_int(value, allow_none=True)
                        any_fields_changed = True
                    elif field == "power":
                        matched_castle["power"] = (
                            parse_power(value) if isinstance(value, str) else sanitise_int(value)
                        )
                        any_fields_changed = True
                    elif field in ["player_level", "command_centre_level", "rallies_30min"]:
                        matched_castle[field] = sanitise_int(value)
                        any_fields_changed = True
                    elif field in ["x", "y"]:
                        matched_castle[field] = sanitise_int(value, allow_none=True)
                        any_fields_changed = True
                    elif field == "locked":
                        # Parse boolean
                        if isinstance(value, str):
                            matched_castle["locked"] = value.lower() in ["true", "1", "yes"]
                        else:
                            matched_castle["locked"] = bool(value)
                        any_fields_changed = True
                    elif field in ["current_trap", "recommended_trap"]:
                        matched_castle[field] = str(value)
                        any_fields_changed = True

                if any_fields_changed:
                    matched_castle["last_updated"] = now

                updated_count += 1

            except Exception as e:
                error_lines.append(f"Row {row_idx}: {str(e)}")
                continue
        else:
            # Add new castle
            try:
                # Determine castle ID
                if csv_id:
                    new_id = csv_id
                else:
                    # Use and increment the castle number counter
                    new_id = f"Castle {next_castle_num}"
                    next_castle_num += 1

                # Check if new ID already exists
                if new_id in existing_by_id:
                    error_lines.append(f"Row {row_idx}: Castle ID '{new_id}' already exists")
                    continue

                # Build new castle with defaults
                new_castle = {
                    "id": new_id,
                    "player": sanitise_player_name(parsed_data.get("player", ""))
                    if "player" in parsed_data
                    else "",
                    "discord_username": sanitise_player_name(
                        parsed_data.get("discord_username", "")
                    )
                    if "discord_username" in parsed_data
                    else "",
                    "power": parse_power(parsed_data.get("power", "0"))
                    if isinstance(parsed_data.get("power"), str)
                    else sanitise_int(parsed_data.get("power", 0)),
                    "player_level": sanitise_int(parsed_data.get("player_level", 0)),
                    "command_centre_level": sanitise_int(
                        parsed_data.get("command_centre_level", 0)
                    ),
                    "attendance": sanitise_int(parsed_data.get("attendance"), allow_none=True)
                    if "attendance" in parsed_data
                    else None,
                    "rallies_30min": sanitise_int(parsed_data.get("rallies_30min", 0)),
                    "preference": normalize_preference(parsed_data.get("preference", "BT1/2")),
                    "current_trap": parsed_data.get("current_trap", ""),
                    "recommended_trap": parsed_data.get("recommended_trap", ""),
                    "priority_score": 0.0,
                    "efficiency_score": 0.0,
                    "round_trip": None,
                    "last_updated": now,
                    "x": sanitise_int(parsed_data.get("x"), allow_none=True)
                    if "x" in parsed_data
                    else None,
                    "y": sanitise_int(parsed_data.get("y"), allow_none=True)
                    if "y" in parsed_data
                    else None,
                    "locked": False,
                }

                existing_castles.append(new_castle)
                existing_by_id[new_id] = new_castle
                if new_castle["player"]:
                    existing_by_player[new_castle["player"].lower()] = new_castle
                added_count += 1

            except Exception as e:
                error_lines.append(f"Row {row_idx}: {str(e)}")
                continue

    if updated_count == 0 and added_count == 0:
        error_msg = "No castles were updated or added."
        if error_lines:
            error_msg += " Errors: " + "; ".join(error_lines[:5])
        return {"success": False, "message": error_msg}

    config["castles"] = existing_castles

    # Recompute priorities and efficiencies
    compute_priority(existing_castles)
    compute_efficiency(config, existing_castles)

    save_config(config)

    # Notify clients to refresh data
    from server.broadcast import notify_config_updated

    await notify_config_updated()

    message = f"Updated {updated_count} castles, added {added_count} new castles"
    if error_lines:
        message += f". {len(error_lines)} errors occurred."

    return {
        "success": True,
        "message": message,
        "errors": error_lines[:10] if error_lines else [],  # Return first 10 errors
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
