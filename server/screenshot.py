"""
Headless browser rendering for map screenshots.

Uses Playwright to render the app in a headless browser and capture screenshots,
ensuring the exact client-side rendering is used server-side.

IMPORTANT: After installing/updating dependencies, run:
    python -m playwright install

This downloads the necessary browser binaries for headless rendering.

Author: Matthew Picone
Date: 2025-12-18
"""

import asyncio
from io import BytesIO

from playwright.async_api import async_playwright


async def render_map_screenshot(base_url: str = "http://localhost:3000") -> BytesIO:
    """Render the map using headless browser and capture screenshot.

    Uses Playwright to open the app in a headless browser, wait for the map
    to render, zoom out to fit all castles, and capture a high-quality screenshot
    of just the canvas grid area.

    Args:
        base_url: Base URL of the server (default: localhost:3000)

    Returns:
        BytesIO object containing high-quality PNG image data of the canvas grid only.

    Raises:
        Exception: If rendering fails or Playwright is not installed.
    """
    async with async_playwright() as p:
        # Launch headless browser with crisp rendering
        browser = await p.chromium.launch(headless=True)

        # Use 1.5x device pixel ratio for crisp output
        # 1920x1440 viewport at 1.5x = 2880x2160 effective pixels
        page = await browser.new_page(
            viewport={"width": 2450, "height": 1600},
            device_scale_factor=5
        )

        try:
            # Navigate to the map application
            # Local rendering is fast, so use shorter timeouts
            await page.goto(f"{base_url}/", wait_until="load", timeout=15000)

            # Wait for the map canvas to be rendered
            await page.wait_for_selector("canvas#map", timeout=5000)

            # Wait for castles to load in the table
            await page.wait_for_function(
                """() => {
                    const table = document.getElementById('castleTableBody');
                    return table && table.children.length > 0;
                }""",
                timeout=5000
            )

            # Give the app time to render the initial view
            await page.wait_for_timeout(500)

            # Execute JavaScript to zoom in to fit all castles with larger view
            await page.evaluate("""() => {
                // Reset view with more zoom for larger map display
                if (typeof viewZoom !== 'undefined' && typeof mapData !== 'undefined') {
                    viewZoom = 0.81;  // ~25% larger for better visibility
                    viewOffsetX = 0;
                    viewOffsetY = (mapData.grid_size * TILE_SIZE) * (Math.SQRT2 / 2);
                    drawMap(mapData);
                }
            }""")

            # Wait for the map to render with new zoom
            await page.wait_for_timeout(300)

            # Get canvas element
            canvas = await page.query_selector("canvas#map")
            if not canvas:
                raise Exception("Canvas element not found")

            # Get the bounding box of the canvas element
            bbox = await canvas.bounding_box()
            if not bbox:
                raise Exception("Could not get canvas bounding box")

            # Capture high-quality screenshot of the canvas
            screenshot_data = await canvas.screenshot(omit_background=False)

            # Return as BytesIO
            return BytesIO(screenshot_data)

        finally:
            await browser.close()


def get_map_screenshot_sync(base_url: str = "http://localhost:3000") -> BytesIO:
    """Synchronous wrapper for render_map_screenshot.

    Uses a thread pool to run the async rendering function synchronously,
    which works better with FastAPI's async context.

    Args:
        base_url: Base URL of the server (default: localhost:3000)

    Returns:
        BytesIO object containing PNG image data.
    """
    import concurrent.futures

    # Run in a separate thread to avoid event loop conflicts
    def run_in_thread():
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(render_map_screenshot(base_url))
        finally:
            loop.close()

    # Use thread pool executor for better compatibility
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_in_thread)
        return future.result(timeout=30)  # 30 second timeout (local rendering is fast)


# Test block - run directly: python server/screenshot.py
if __name__ == "__main__":
    import sys

    print("🎬 Starting map screenshot test...")
    print("=" * 60)

    # Get base URL from command line argument or use default
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"
    print(f"📍 Target URL: {base_url}")
    print(f"⏳ Rendering map screenshot (this may take 30-90 seconds)...\n")

    try:
        # Capture screenshot
        screenshot_buf = get_map_screenshot_sync(base_url=base_url)

        # Save to file
        output_path = "map_screenshot.png"
        with open(output_path, "wb") as f:
            f.write(screenshot_buf.getvalue())

        # Get file size
        file_size_kb = len(screenshot_buf.getvalue()) / 1024

        print("=" * 60)
        print(f"✅ Screenshot captured successfully!")
        print(f"💾 Saved to: {output_path}")
        print(f"📏 File size: {file_size_kb:.2f} KB")
        print("=" * 60)

    except Exception as e:
        print("=" * 60)
        print(f"❌ Error capturing screenshot:")
        print(f"{type(e).__name__}: {str(e)}")
        print("=" * 60)
        sys.exit(1)
