"""User context management for audit logging.

This module provides simple user identification for tracking
who makes changes. Uses headers or session-based identification.
"""

from fastapi import Header, Request
from typing import Optional


def get_current_user(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    request: Request = None,
) -> str:
    """Get current user identifier from request.

    Args:
        x_user_id: User ID from X-User-ID header.
        request: FastAPI request object.

    Returns:
        User identifier string. Defaults to 'anonymous' if not provided.
    """
    # Try header first
    if x_user_id:
        return x_user_id

    # Try to get from session/cookies if implemented
    # For now, return a simple identifier based on client
    if request:
        # Use client host as fallback identifier
        client_host = request.client.host if request.client else "unknown"
        return f"user-{client_host}"

    return "anonymous"
