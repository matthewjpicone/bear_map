"""
Castle placement algorithms.

This module contains logic for automatically placing castles on the grid,
optimizing for spacing and avoiding overlaps.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
"""

from typing import List, Dict

from .config import load_config, save_config
from .validation import is_within_bounds, check_castle_overlap


async def auto_place_castles() -> Dict[str, int]:
    """Auto-place castles on the grid using a simple algorithm.

    This is a placeholder implementation that arranges castles in a grid pattern.
    A more sophisticated algorithm could optimize based on efficiency, bear trap
    proximity, etc.

    Returns:
        Dictionary with success status and number of castles placed.
    """
    config = load_config()
    castles = config.get("castles", [])
    grid_size = config.get("grid_size", 28)

    # Simple grid placement: arrange castles in rows with spacing
    placed_count = 0
    row_spacing = 3
    col_spacing = 3
    x, y = 1, 1

    for castle in castles:
        if castle.get("locked", False):
            continue

        # Find next available position
        while True:
            has_overlap, _ = check_castle_overlap(
                x, y, castles, exclude_id=castle.get("id")
            )
            if not has_overlap and is_within_bounds(x, y, grid_size, width=2, height=2):
                castle["x"] = x
                castle["y"] = y
                placed_count += 1
                break

            # Move to next position
            x += col_spacing
            if x + 2 > grid_size:
                x = 1
                y += row_spacing
                if y + 2 > grid_size:
                    # No more space
                    break

            if y + 2 > grid_size:
                break

    save_config(config)

    return {"success": True, "placed": placed_count}
