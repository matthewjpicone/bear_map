"""
Map export module for server-side rendering.

This module provides endpoints for exporting the map as a PNG image using
headless browser rendering via Playwright.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-18
"""

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from playwright.async_api import async_playwright, Browser, TimeoutError as PlaywrightTimeoutError

from logic.config import load_config


router = APIRouter()

# Global browser instance for reuse
_browser: Optional[Browser] = None
_browser_lock = asyncio.Lock()


async def get_browser() -> Browser:
    """Get or create a singleton headless browser instance.
    
    Returns:
        Browser instance.
    """
    global _browser
    
    async with _browser_lock:
        if _browser is None or not _browser.is_connected():
            playwright = await async_playwright().start()
            _browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                ]
            )
        return _browser


@router.get("/api/map/export.png")
async def export_map_png():
    """Export the current map as a PNG image using headless browser rendering.
    
    This endpoint:
    1. Loads the current map configuration
    2. Launches a headless browser
    3. Loads the map page in render mode (?render=1)
    4. Injects the map data and calls renderMapForExport()
    5. Waits for rendering to complete
    6. Takes a screenshot of the canvas
    7. Returns the PNG image
    
    Returns:
        PNG image with content-type: image/png
        
    Raises:
        HTTPException: If rendering fails or times out
    """
    try:
        # Load the current map configuration
        config = load_config()
        
        # Update round trip times for all castles
        from logic.placement import update_all_round_trip_times
        update_all_round_trip_times(config.get("castles", []), config.get("bear_traps", []))
        
        # Compute priority and efficiency
        from logic.scoring import compute_priority, compute_efficiency
        castles = config.get("castles", [])
        compute_priority(castles)
        compute_efficiency(config, castles)
        
        # Prepare map data
        map_data = {
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
        
        # Get browser instance
        browser = await get_browser()
        
        # Create a new page with fixed viewport
        context = await browser.new_context(
            viewport={'width': 1600, 'height': 1600},
            device_scale_factor=1,
            locale='en-US',
            timezone_id='UTC',
        )
        
        page = await context.new_page()
        
        try:
            # Load the map page in render mode
            # Use localhost:8000 as the default for local development
            # In production, this should be the actual server URL
            await page.goto('http://localhost:8000/?render=1', wait_until='networkidle', timeout=10000)
            
            # Inject map data and call renderMapForExport
            await page.evaluate(f"""
                window.renderMapForExport({json.dumps(map_data)});
            """)
            
            # Wait for rendering to complete (max 10 seconds)
            await page.wait_for_function(
                'window.__MAP_RENDER_DONE__ === true',
                timeout=10000
            )
            
            # Take screenshot of the canvas element
            canvas = await page.query_selector('#map')
            if not canvas:
                raise HTTPException(status_code=500, detail="Canvas element not found")
            
            screenshot_bytes = await canvas.screenshot(type='png')
            
            return Response(
                content=screenshot_bytes,
                media_type='image/png',
                headers={
                    'Content-Disposition': 'attachment; filename=map-export.png',
                    'Cache-Control': 'no-cache',
                }
            )
            
        finally:
            # Clean up the context
            await context.close()
            
    except PlaywrightTimeoutError as e:
        raise HTTPException(
            status_code=504,
            detail=f"Rendering timeout: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export map: {str(e)}"
        )


async def cleanup_browser():
    """Cleanup the browser instance on shutdown."""
    global _browser
    if _browser is not None:
        await _browser.close()
        _browser = None
