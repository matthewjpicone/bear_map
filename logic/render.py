"""
Server-side map rendering for image generation.

This module provides functionality to generate PNG images of the bear map
that match the client-side JavaScript canvas rendering exactly.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
"""

import math
import io
from typing import Dict, List, Any, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont


# Constants matching client-side app.js
TILE_SIZE = 40
ISO_DEG = 45  # 45 degree rotation
DEFAULT_GRID_SIZE = 28


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string to RGB tuple.
    
    Args:
        hex_color: Hex color string (e.g., "#16a34a").
        
    Returns:
        RGB tuple (r, g, b).
    """
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def hex_to_rgba(hex_color: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    """Convert hex color string to RGBA tuple.
    
    Args:
        hex_color: Hex color string (e.g., "#16a34a").
        alpha: Alpha value (0-255).
        
    Returns:
        RGBA tuple (r, g, b, a).
    """
    rgb = hex_to_rgb(hex_color)
    return rgb + (alpha,)


def get_efficiency_color(efficiency_score: Optional[float], efficiency_scale: List[Dict]) -> str:
    """Get color for a given efficiency score.
    
    Args:
        efficiency_score: The efficiency score value.
        efficiency_scale: List of efficiency scale tiers with 'max' and 'color'.
        
    Returns:
        Hex color string.
    """
    if efficiency_score is None:
        return "#374151"
    
    if not efficiency_scale:
        return "#374151"
    
    for tier in efficiency_scale:
        if efficiency_score <= tier['max']:
            return tier['color']
    
    return efficiency_scale[-1]['color']


def rotate_point(x: float, y: float, angle_deg: float) -> Tuple[float, float]:
    """Rotate a point around the origin.
    
    Args:
        x: X coordinate.
        y: Y coordinate.
        angle_deg: Rotation angle in degrees.
        
    Returns:
        Rotated (x, y) coordinates.
    """
    angle_rad = math.radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    
    new_x = x * cos_a - y * sin_a
    new_y = x * sin_a + y * cos_a
    
    return new_x, new_y


def draw_rotated_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    position: Tuple[float, float],
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int, int],
    rotation: float = 0
) -> None:
    """Draw rotated text on an image.
    
    Args:
        draw: ImageDraw object.
        text: Text to draw.
        position: (x, y) position.
        font: Font to use.
        fill: RGBA color tuple.
        rotation: Rotation angle in degrees (counter-clockwise).
    """
    if rotation == 0:
        # Get text bounding box for centering
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Center the text
        x = position[0] - text_width / 2
        y = position[1] - text_height / 2
        
        draw.text((x, y), text, font=font, fill=fill)
    else:
        # Create a temporary image for the text
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Add padding for rotation
        padding = int(max(text_width, text_height) * 1.5)
        txt_img = Image.new('RGBA', (padding, padding), (0, 0, 0, 0))
        txt_draw = ImageDraw.Draw(txt_img)
        
        # Draw text centered in the temporary image
        txt_draw.text((padding // 2 - text_width // 2, padding // 2 - text_height // 2), 
                     text, font=font, fill=fill)
        
        # Rotate the temporary image
        txt_img = txt_img.rotate(-rotation, expand=False)
        
        # Paste onto main image
        draw._image.paste(txt_img, (int(position[0] - padding // 2), int(position[1] - padding // 2)), txt_img)


def render_map_to_image(config: Dict[str, Any], show_grid: bool = True) -> bytes:
    """Render the map to a PNG image that matches the client-side rendering.
    
    Args:
        config: Map configuration dictionary.
        show_grid: Whether to show the grid lines.
        
    Returns:
        PNG image as bytes.
    """
    grid_size = config.get('grid_size', DEFAULT_GRID_SIZE)
    efficiency_scale = config.get('efficiency_scale', [])
    banners = config.get('banner', [])  # Note: config uses 'banner' not 'banners'
    bear_traps = config.get('bear_traps', [])
    castles = config.get('castles', [])
    
    # Calculate canvas size to fit the rotated grid with padding
    # After 45° rotation, a square grid becomes wider (diagonal = side * sqrt(2))
    grid_pixel_size = grid_size * TILE_SIZE
    diagonal = grid_pixel_size * math.sqrt(2)
    
    # Use generous padding to ensure everything fits
    padding = 200
    canvas_width = int(diagonal + padding * 2)
    canvas_height = int(diagonal + padding * 2)
    
    # Create image with dark background to match client theme
    # The client uses a dark background (#0f172a or similar)
    img = Image.new('RGBA', (canvas_width, canvas_height), (15, 23, 42, 255))
    draw = ImageDraw.Draw(img)
    
    # Calculate center point - this is where the rotated grid will be centered
    center_x = canvas_width // 2
    center_y = canvas_height // 2
    
    # Calculate viewOffset to match client-side centering
    # Client uses: viewOffsetY = (mapData.grid_size * TILE_SIZE) * (Math.SQRT2 / 2)
    view_offset_x = 0
    view_offset_y = grid_pixel_size * (math.sqrt(2) / 2)
    
    def transform_coords(gx: float, gy: float) -> Tuple[float, float]:
        """Transform grid coordinates to screen coordinates with 45° rotation.
        
        Matches the client-side transformation exactly:
        1. Translate by -viewOffset
        2. Rotate 45° around origin
        3. Translate to canvas center
        
        Args:
            gx: Grid X coordinate (in pixels).
            gy: Grid Y coordinate (in pixels).
            
        Returns:
            Screen (x, y) coordinates.
        """
        # Step 1: Apply view offset (like client's translateSelf(-viewOffsetX, -viewOffsetY))
        tx = gx - view_offset_x
        ty = gy - view_offset_y
        
        # Step 2: Rotate 45° around origin
        rx, ry = rotate_point(tx, ty, ISO_DEG)
        
        # Step 3: Translate to center of canvas
        sx = rx + center_x
        sy = ry + center_y
        
        return sx, sy
    
    # Load a simple font (fall back to default if not available)
    try:
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except OSError:
        # Fall back to default font if DejaVu not available
        font_small = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_large = ImageFont.load_default()
    
    # Draw grid
    if show_grid:
        for x in range(grid_size + 1):
            for y in range(grid_size + 1):
                # Draw horizontal lines
                if y < grid_size:
                    x1, y1 = transform_coords(x * TILE_SIZE, y * TILE_SIZE)
                    x2, y2 = transform_coords(x * TILE_SIZE, (y + 1) * TILE_SIZE)
                    draw.line([(x1, y1), (x2, y2)], fill=(204, 204, 204, 255), width=1)
                
                # Draw vertical lines
                if x < grid_size:
                    x1, y1 = transform_coords(x * TILE_SIZE, y * TILE_SIZE)
                    x2, y2 = transform_coords((x + 1) * TILE_SIZE, y * TILE_SIZE)
                    draw.line([(x1, y1), (x2, y2)], fill=(204, 204, 204, 255), width=1)
    
    # Draw banners
    for banner in banners:
        if banner.get('x') is None or banner.get('y') is None:
            continue
        
        bx = banner['x']
        by = banner['y']
        
        # Draw 7x7 influence area (light green) - always show in static image
        # Client shows this only when dragging, but static image should always show
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                ix = bx + dx
                iy = by + dy
                if 0 <= ix < grid_size and 0 <= iy < grid_size:
                    corners = [
                        transform_coords(ix * TILE_SIZE, iy * TILE_SIZE),
                        transform_coords((ix + 1) * TILE_SIZE, iy * TILE_SIZE),
                        transform_coords((ix + 1) * TILE_SIZE, (iy + 1) * TILE_SIZE),
                        transform_coords(ix * TILE_SIZE, (iy + 1) * TILE_SIZE),
                    ]
                    draw.polygon(corners, fill=(34, 197, 94, 89))  # rgba(34, 197, 94, 0.35)
        
        # Draw banner rectangle (blue) - px = pos.x * TILE_SIZE, py = pos.y * TILE_SIZE
        px = bx * TILE_SIZE
        py = by * TILE_SIZE
        corners = [
            transform_coords(px, py),
            transform_coords(px + TILE_SIZE, py),
            transform_coords(px + TILE_SIZE, py + TILE_SIZE),
            transform_coords(px, py + TILE_SIZE),
        ]
        draw.polygon(corners, fill=(30, 58, 138, 255))  # #1e3a8a
        
        # Draw border (white)
        for i in range(len(corners)):
            draw.line([corners[i], corners[(i + 1) % len(corners)]], fill=(255, 255, 255, 255), width=1)
        
        # Draw banner label (rotated -45°) at center of tile
        cx, cy = transform_coords(px + TILE_SIZE / 2, py + TILE_SIZE / 2)
        banner_id = str(banner.get('id', ''))
        draw_rotated_text(draw, banner_id, (cx, cy), font_large, (255, 255, 255, 255), rotation=45)
        
        # Draw lock indicator if locked (below center)
        if banner.get('locked', False):
            lock_offset = TILE_SIZE * 0.45
            lock_x, lock_y = transform_coords(px + TILE_SIZE / 2, py + TILE_SIZE / 2 + lock_offset)
            draw_rotated_text(draw, "🔒", (lock_x, lock_y), font_medium, (255, 255, 255, 255), rotation=45)
    
    # Draw bear traps
    for bear in bear_traps:
        if bear.get('x') is None or bear.get('y') is None:
            continue
        
        bx = bear['x']
        by = bear['y']
        
        # Draw 3x3 influence area (gray) - centered on bear position
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                ix = bx + dx
                iy = by + dy
                if 0 <= ix < grid_size and 0 <= iy < grid_size:
                    corners = [
                        transform_coords(ix * TILE_SIZE, iy * TILE_SIZE),
                        transform_coords((ix + 1) * TILE_SIZE, iy * TILE_SIZE),
                        transform_coords((ix + 1) * TILE_SIZE, (iy + 1) * TILE_SIZE),
                        transform_coords(ix * TILE_SIZE, (iy + 1) * TILE_SIZE),
                    ]
                    draw.polygon(corners, fill=(120, 120, 120, 89))  # rgba(120,120,120,0.35)
        
        # Draw bear circle - center at pos.x * TILE_SIZE + TILE_SIZE / 2
        px = bx * TILE_SIZE + TILE_SIZE / 2
        py = by * TILE_SIZE + TILE_SIZE / 2
        cx, cy = transform_coords(px, py)
        radius = TILE_SIZE * 1.35
        
        # Determine fill color based on locked state
        if bear.get('locked', False):
            fill_color = (30, 41, 59, 255)  # #1e293b
        else:
            fill_color = (10, 31, 68, 255)  # #0a1f44
        
        # Draw circle
        draw.ellipse(
            [(cx - radius, cy - radius), (cx + radius, cy + radius)],
            fill=fill_color
        )
        
        # Draw bear label (rotated -45°) at center
        bear_id = str(bear.get('id', ''))
        draw_rotated_text(draw, bear_id, (cx, cy), font_large, (255, 255, 255, 255), rotation=45)
        
        # Draw lock indicator if locked (below center)
        if bear.get('locked', False):
            lock_offset = TILE_SIZE * 0.45
            lock_px = px
            lock_py = py + lock_offset
            lock_x, lock_y = transform_coords(lock_px, lock_py)
            draw_rotated_text(draw, "🔒", (lock_x, lock_y), font_small, (255, 255, 255, 255), rotation=45)
    
    # Draw castles
    for castle in castles:
        if castle.get('x') is None or castle.get('y') is None:
            continue
        
        cx_grid = castle['x']
        cy_grid = castle['y']
        
        # Get efficiency color
        efficiency_score = castle.get('efficiency_score')
        color_hex = get_efficiency_color(efficiency_score, efficiency_scale)
        color_rgb = hex_to_rgb(color_hex)
        
        # Castle position: px = pos.x * TILE_SIZE, py = pos.y * TILE_SIZE
        # Castle size: TILE_SIZE * 2 (2x2 tiles)
        px = cx_grid * TILE_SIZE
        py = cy_grid * TILE_SIZE
        size = TILE_SIZE * 2
        
        # Draw castle rectangle with 2-pixel padding (px + 2, py + 2, size - 4, size - 4)
        corners = [
            transform_coords(px + 2, py + 2),
            transform_coords(px + size - 2, py + 2),
            transform_coords(px + size - 2, py + size - 2),
            transform_coords(px + 2, py + size - 2),
        ]
        draw.polygon(corners, fill=color_rgb + (255,))
        
        # Draw border
        border_color = (229, 231, 235, 255)  # #e5e7eb
        for i in range(len(corners)):
            draw.line([corners[i], corners[(i + 1) % len(corners)]], fill=border_color, width=1)
        
        # Calculate center of castle for text: px + size / 2, py + size / 2
        center_px = px + size / 2
        center_py = py + size / 2
        cx, cy = transform_coords(center_px, center_py)
        
        # Draw castle text (rotated -45°)
        player = str(castle.get('player', ''))[:20]  # Limit to 20 chars
        player_level = castle.get('player_level', '-')
        preference = castle.get('preference', '')
        
        # Player name (bold, 10px) at y offset -6
        text_px = center_px
        text_py = center_py - 6
        text_x, text_y = transform_coords(text_px, text_py)
        draw_rotated_text(draw, player, (text_x, text_y), font_small, (255, 255, 255, 255), rotation=45)
        
        # Level (12px) at y offset +10
        text_px = center_px
        text_py = center_py + 10
        text_x, text_y = transform_coords(text_px, text_py)
        level_text = f"Lv {player_level}"
        draw_rotated_text(draw, level_text, (text_x, text_y), font_medium, (255, 255, 255, 255), rotation=45)
        
        # Preference (11px) at y offset +24
        text_px = center_px
        text_py = center_py + 24
        text_x, text_y = transform_coords(text_px, text_py)
        draw_rotated_text(draw, str(preference), (text_x, text_y), font_small, (255, 255, 255, 255), rotation=45)
        
        # Draw lock indicator if locked (at px + size / 2, py + size + 8, then offset by 35, 5 after rotation)
        if castle.get('locked', False):
            lock_px = center_px + 35  # x offset in rotated space
            lock_py = py + size + 8 + 5  # y offset
            lock_x, lock_y = transform_coords(lock_px, lock_py)
            draw_rotated_text(draw, "🔒", (lock_x, lock_y), font_small, (255, 255, 255, 255), rotation=45)
    
    # Convert to PNG bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return img_bytes.getvalue()
