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
from io import StringIO, BytesIO
from typing import Dict, Any
from datetime import datetime
import math

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from PIL import Image, ImageDraw

from logic.config import load_config, save_config
from logic.scoring import compute_priority, compute_efficiency


TILE_SIZE = 40


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


def efficiency_color(value):
    """Get color for efficiency value."""
    if value is None or not isinstance(value, (int, float)):
        return "#374151"
    efficiency_scale = [
        {"max": 6, "color": "#16a34a"},
        {"max": 10, "color": "#2563eb"},
        {"max": 15, "color": "#64748b"},
        {"max": float('inf'), "color": "#1f2937"}
    ]
    for tier in efficiency_scale:
        if value <= tier["max"]:
            return tier["color"]
    return efficiency_scale[-1]["color"]


def grid_to_screen_img(gx, gy, zoom, offsetX, offsetY, canvas_w, canvas_h):
    """Convert grid coordinates to screen coordinates matching app.js.

    Applies transformations in exact order:
    1. translate(centerX, centerY)
    2. scale(zoom, zoom)
    3. translate(-offsetX, -offsetY)
    4. rotate(45deg)
    """
    centerX = canvas_w / 2
    centerY = canvas_h / 2

    # Grid space to world space (in tiles)
    px = gx * TILE_SIZE
    py = gy * TILE_SIZE

    # Apply offset (in grid space, before zoom)
    px -= offsetX * TILE_SIZE
    py -= offsetY * TILE_SIZE

    # Apply zoom
    px *= zoom
    py *= zoom

    # Apply 45 degree rotation
    rad = math.radians(45)
    cos = math.cos(rad)
    sin = math.sin(rad)
    rx = px * cos - py * sin
    ry = px * sin + py * cos

    # Apply center translation
    rx += centerX
    ry += centerY

    return rx, ry


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


@router.get("/api/download_map_image")
def download_map_image():
    """Download the current map as a PNG image.

    Renders the map server-side matching app.js exactly.

    Returns:
        PNG image file.
    """
    try:
        from PIL import ImageFont
        config = load_config()
        castles = config.get("castles", [])
        bear_traps = config.get("bear_traps", [])
        banners = config.get("banners", [])
        grid_size = config.get("grid_size", 28)

        canvas_w, canvas_h = 1600, 1600

        # Compute zoom and offset to fit all castles
        placed_castles = [c for c in castles if c.get("x") is not None and c.get("y") is not None]
        if not placed_castles:
            # Empty image
            img = Image.new('RGB', (canvas_w, canvas_h), (255, 255, 255))
            draw = ImageDraw.Draw(img)
            draw.text((800, 800), "No castles placed", fill=(0, 0, 0))
            buf = BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            return StreamingResponse(buf, media_type="image/png", headers={"Content-Disposition": "attachment; filename=map.png"})

        # Calculate bounds in grid coordinates
        min_gx = min(c["x"] for c in placed_castles)
        max_gx = max(c["x"] for c in placed_castles)
        min_gy = min(c["y"] for c in placed_castles)
        max_gy = max(c["y"] for c in placed_castles)

        # Add padding in grid space
        min_gx = max(0, min_gx - 2)
        max_gx = min(grid_size - 1, max_gx + 3)
        min_gy = max(0, min_gy - 2)
        max_gy = min(grid_size - 1, max_gy + 3)

        # Center point in grid coordinates
        center_gx = (min_gx + max_gx) / 2
        center_gy = (min_gy + max_gy) / 2

        # Calculate zoom to fit bounds
        # After rotation, width in screen space is approximately (width_tiles + height_tiles) * tile_size * 0.707
        width_tiles = max_gx - min_gx + 1
        height_tiles = max_gy - min_gy + 1

        approx_screen_size = (width_tiles + height_tiles) * TILE_SIZE * 0.707
        zoom = (canvas_w * 0.85) / approx_screen_size if approx_screen_size > 0 else 1.0
        zoom = min(zoom, 2.0)  # Cap zoom

        # offsetX and offsetY are in GRID coordinates, not screen
        offsetX = center_gx
        offsetY = center_gy

        # Create image
        img = Image.new('RGB', (canvas_w, canvas_h), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Draw grid lightly
        for x in range(max(0, min_gx - 1), min(grid_size, max_gx + 2)):
            for y in range(max(0, min_gy - 1), min(grid_size, max_gy + 2)):
                sx, sy = grid_to_screen_img(x, y, zoom, offsetX, offsetY, canvas_w, canvas_h)
                tile_sz = TILE_SIZE * zoom
                draw.rectangle([sx, sy, sx + tile_sz, sy + tile_sz], outline=(200, 200, 200), width=1)

        # Draw banners
        for banner in banners:
            if banner.get("x") is not None and banner.get("y") is not None:
                sx, sy = grid_to_screen_img(banner["x"], banner["y"], zoom, offsetX, offsetY, canvas_w, canvas_h)
                tile_sz = TILE_SIZE * zoom
                draw.rectangle([sx, sy, sx + tile_sz, sy + tile_sz], fill=(30, 58, 138))

        # Draw bear traps
        for bear in bear_traps:
            if bear.get("x") is not None and bear.get("y") is not None:
                cx, cy = grid_to_screen_img(bear["x"], bear["y"], zoom, offsetX, offsetY, canvas_w, canvas_h)
                radius = TILE_SIZE * 1.35 * zoom
                draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                           fill=(10, 31, 68))

        # Draw castles with text
        for castle in castles:
            if castle.get("x") is not None and castle.get("y") is not None:
                sx, sy = grid_to_screen_img(castle["x"], castle["y"], zoom, offsetX, offsetY, canvas_w, canvas_h)
                size = TILE_SIZE * 2 * zoom

                # Draw castle rectangle
                color = efficiency_color(castle.get("efficiency_score"))
                color = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
                draw.rectangle([sx + 2, sy + 2, sx + size - 2, sy + size - 2], fill=color)

                # Draw border
                draw.rectangle([sx + 2, sy + 2, sx + size - 2, sy + size - 2],
                             outline=(229, 231, 235), width=1)

                # Draw text
                try:
                    font = ImageFont.load_default()

                    # Player name
                    player = castle.get("player", "")[:15]
                    if player and size > 20:
                        draw.text((sx + size/2, sy + size/2 - 6), player, fill=(255, 255, 255),
                                font=font, anchor="mm")

                    # Level
                    level = castle.get("player_level", 0)
                    if size > 20:
                        draw.text((sx + size/2, sy + size/2 + 4), f"Lv {level}", fill=(255, 255, 255),
                                font=font, anchor="mm")

                    # Preference
                    pref = castle.get("preference", "")
                    if pref and size > 20:
                        draw.text((sx + size/2, sy + size/2 + 12), str(pref)[:8], fill=(255, 255, 255),
                                font=font, anchor="mm")
                except Exception:
                    pass  # Skip text if font fails

                # Locked indicator
                if castle.get("locked") and size > 15:
                    try:
                        draw.text((sx + size - 8, sy + size - 8), "🔒", fill=(255, 255, 255),
                                anchor="mm")
                    except:
                        pass

        # Save to bytes
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png",
                               headers={"Content-Disposition": "attachment; filename=map.png"})

    except Exception as e:
        print(f"Error generating image: {e}")
        import traceback
        traceback.print_exc()
        # Return error image
        error_img = Image.new('RGB', (1600, 1600), (255, 0, 0))
        draw = ImageDraw.Draw(error_img)
        draw.text((10, 10), f"Error: {str(e)[:80]}", fill=(255, 255, 255))
        buf = BytesIO()
        error_img.save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png",
                               headers={"Content-Disposition": "attachment; filename=error.png"})
