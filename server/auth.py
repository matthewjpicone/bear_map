"""Discord OAuth authentication module.

This module handles Discord OAuth2 authentication for the Bear Planner application.
It provides login, callback, and session management functionality.
"""

import os
from typing import Optional

from authlib.integrations.starlette_client import OAuth
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer
from starlette.middleware.sessions import SessionMiddleware


# Discord OAuth configuration
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv(
    "DISCORD_REDIRECT_URI", "http://localhost:8000/auth/callback"
)
SESSION_SECRET_KEY = os.getenv(
    "SESSION_SECRET_KEY", "default-secret-key-change-in-production"
)

# Session serializer for secure session management
serializer = URLSafeTimedSerializer(SESSION_SECRET_KEY)

# OAuth client setup
oauth = OAuth()
oauth.register(
    name="discord",
    client_id=DISCORD_CLIENT_ID,
    client_secret=DISCORD_CLIENT_SECRET,
    access_token_url="https://discord.com/api/oauth2/token",
    access_token_params=None,
    authorize_url="https://discord.com/api/oauth2/authorize",
    authorize_params=None,
    api_base_url="https://discord.com/api/",
    client_kwargs={"scope": "identify"},
)


def get_session_middleware():
    """Get SessionMiddleware instance for FastAPI app.

    Returns:
        SessionMiddleware configured with secret key.
    """
    return SessionMiddleware(
        app=None,  # Will be set by FastAPI
        secret_key=SESSION_SECRET_KEY,
        session_cookie="bear_session",
        max_age=86400 * 7,  # 7 days
        same_site="lax",
        https_only=False,  # Set to True in production with HTTPS
    )


async def get_current_user(request: Request) -> Optional[dict]:
    """Get current authenticated user from session.

    Args:
        request: The FastAPI request object.

    Returns:
        User dictionary if authenticated, None otherwise.
    """
    user_data = request.session.get("user")
    if not user_data:
        return None
    return user_data


async def require_auth(request: Request) -> dict:
    """Dependency to require authentication for endpoints.

    Args:
        request: The FastAPI request object.

    Returns:
        User dictionary if authenticated.

    Raises:
        HTTPException: 401 if not authenticated.
    """
    user = await get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def login(request: Request):
    """Redirect to Discord OAuth login page.

    Args:
        request: The FastAPI request object.

    Returns:
        RedirectResponse to Discord OAuth authorization URL.
    """
    redirect_uri = DISCORD_REDIRECT_URI
    return await oauth.discord.authorize_redirect(request, redirect_uri)


async def callback(request: Request):
    """Handle Discord OAuth callback.

    Args:
        request: The FastAPI request object.

    Returns:
        RedirectResponse to home page after successful authentication.

    Raises:
        HTTPException: 400 if OAuth callback fails.
    """
    try:
        token = await oauth.discord.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth callback failed: {str(e)}",
        )

    # Fetch user info from Discord
    resp = await oauth.discord.get("users/@me", token=token)
    user_data = resp.json()

    # Store user info in session
    request.session["user"] = {
        "id": user_data.get("id"),
        "username": user_data.get("username"),
        "discriminator": user_data.get("discriminator"),
        "avatar": user_data.get("avatar"),
        "email": user_data.get("email"),
    }

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


async def logout(request: Request):
    """Logout the current user.

    Args:
        request: The FastAPI request object.

    Returns:
        RedirectResponse to home page after logout.
    """
    request.session.clear()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


def is_authenticated(request: Request) -> bool:
    """Check if the current request is authenticated.

    Args:
        request: The FastAPI request object.

    Returns:
        True if authenticated, False otherwise.
    """
    return request.session.get("user") is not None
