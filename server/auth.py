"""Authentication and workspace management module.

This module handles Discord OAuth authentication and workspace-based access control.
Each workspace has a whitelist of approved Discord user IDs.
"""

import os
import json
from typing import Optional, Set
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta

# JWT configuration
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

security = HTTPBearer(auto_error=False)


class WorkspaceManager:
    """Manages workspace configurations and access control."""

    def __init__(self, config_path: str):
        """Initialize workspace manager.

        Args:
            config_path: Path to the configuration file.
        """
        self.config_path = config_path
        self._workspaces = self._load_workspaces()

    def _load_workspaces(self) -> dict:
        """Load workspace configurations from config file.

        Returns:
            Dictionary of workspace configurations.
        """
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("workspaces", {})
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def get_workspace(self, workspace_id: str) -> Optional[dict]:
        """Get workspace configuration by ID.

        Args:
            workspace_id: The workspace identifier.

        Returns:
            Workspace configuration or None if not found.
        """
        return self._workspaces.get(workspace_id)

    def is_user_authorized(
        self, workspace_id: str, discord_user_id: str
    ) -> bool:
        """Check if a Discord user is authorized for a workspace.

        Args:
            workspace_id: The workspace identifier.
            discord_user_id: The Discord user ID to check.

        Returns:
            True if authorized, False otherwise.
        """
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            return False

        whitelist = workspace.get("whitelist", [])
        return discord_user_id in whitelist

    def get_user_workspaces(self, discord_user_id: str) -> Set[str]:
        """Get all workspaces a user is authorized for.

        Args:
            discord_user_id: The Discord user ID.

        Returns:
            Set of workspace IDs the user can access.
        """
        authorized = set()
        for workspace_id, workspace in self._workspaces.items():
            if discord_user_id in workspace.get("whitelist", []):
                authorized.add(workspace_id)
        return authorized

    def list_workspaces(self) -> dict:
        """List all workspace configurations.

        Returns:
            Dictionary of all workspaces.
        """
        return self._workspaces


def create_access_token(
    discord_user_id: str, username: str, workspaces: Set[str]
) -> str:
    """Create a JWT access token for a user.

    Args:
        discord_user_id: The Discord user ID.
        username: The Discord username.
        workspaces: Set of workspace IDs the user can access.

    Returns:
        JWT token string.
    """
    payload = {
        "discord_id": discord_user_id,
        "username": username,
        "workspaces": list(workspaces),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token.

    Args:
        token: The JWT token string.

    Returns:
        Decoded payload or None if invalid.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    """Get the current authenticated user from JWT token.

    Args:
        credentials: HTTP Bearer token credentials.

    Returns:
        User payload or None if not authenticated.
    """
    if not credentials:
        return None

    token = credentials.credentials
    payload = decode_access_token(token)
    return payload


async def require_authentication(
    user: Optional[dict] = Depends(get_current_user),
) -> dict:
    """Require user authentication.

    Args:
        user: Current user payload.

    Returns:
        User payload.

    Raises:
        HTTPException: If user is not authenticated.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def require_workspace_access(
    workspace_id: str,
    user: dict = Depends(require_authentication),
) -> dict:
    """Require user to have access to a specific workspace.

    Args:
        workspace_id: The workspace to check access for.
        user: Current user payload.

    Returns:
        User payload.

    Raises:
        HTTPException: If user doesn't have access to the workspace.
    """
    user_workspaces = set(user.get("workspaces", []))
    if workspace_id not in user_workspaces:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied to workspace: {workspace_id}",
        )
    return user


def get_user_workspace_filter(user: Optional[dict]) -> Optional[Set[str]]:
    """Get workspace filter for the current user.

    Args:
        user: Current user payload or None.

    Returns:
        Set of workspace IDs user can access, or None for admin/unauthenticated.
    """
    if not user:
        # No authentication = legacy mode, allow all
        return None
    return set(user.get("workspaces", []))
