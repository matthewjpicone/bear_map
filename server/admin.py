"""
Admin routes for configuration management.

This module provides administrative endpoints for directly editing the
config.json file through a web interface.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2026-01-03
"""

import json
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from logic.config import CONFIG_PATH

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")


class ConfigUpdate(BaseModel):
    """Request model for updating configuration."""

    content: str


@router.get("/admin", response_class=HTMLResponse)
def admin_page():
    """Serve the admin configuration editor page.

    Returns:
        HTML page for editing config.json.
    """
    template_path = os.path.join(TEMPLATE_DIR, "admin.html")
    return FileResponse(template_path)


@router.get("/api/admin/config")
def get_config():
    """Get the raw config.json content.

    Returns:
        Dictionary containing the raw JSON content as a string.

    Raises:
        HTTPException: If config file cannot be read.
    """
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Config file not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error reading config file: {str(e)}"
        )


@router.post("/api/admin/config")
async def update_config(data: ConfigUpdate):
    """Update the config.json file with new content.

    Validates that the content is valid JSON before saving.

    Args:
        data: ConfigUpdate object containing the new JSON content.

    Returns:
        Success message.

    Raises:
        HTTPException: If JSON is invalid or file cannot be saved.
    """
    try:
        # Validate JSON
        parsed_config = json.loads(data.content)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    try:
        # Save the config
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            # Use indent=2 to match existing format
            json.dump(parsed_config, f, indent=2, ensure_ascii=False)

        # Notify connected clients about the update
        from server.broadcast import notify_config_updated

        await notify_config_updated()

        return {"success": True, "message": "Configuration updated successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error saving config file: {str(e)}"
        )
