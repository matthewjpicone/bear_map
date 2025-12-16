"""Discord OAuth2 authentication module.

This module handles Discord OAuth2 authentication flow for user login.
Uses Authlib for OAuth2 integration and itsdangerous for secure session management.
"""

import os
import secrets
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Cookie
from fastapi.responses import RedirectResponse, JSONResponse
from authlib.integrations.starlette_client import OAuth
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

router = APIRouter()

# Load Discord OAuth2 configuration from environment variables
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:8000/auth/callback")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")

# Validate required environment variables
if not SESSION_SECRET_KEY:
    SESSION_SECRET_KEY = secrets.token_urlsafe(32)
    print(
        "WARNING: SESSION_SECRET_KEY not set. Using temporary key. Set this in .env for production."
    )

# Session serializer for secure cookie signing
serializer = URLSafeTimedSerializer(SESSION_SECRET_KEY)

# Session configuration
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days in seconds
COOKIE_NAME = "session"

# OAuth2 configuration
oauth = OAuth()

if DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET:
    oauth.register(
        name="discord",
        client_id=DISCORD_CLIENT_ID,
        client_secret=DISCORD_CLIENT_SECRET,
        authorize_url="https://discord.com/api/oauth2/authorize",
        authorize_params={"scope": "identify"},
        access_token_url="https://discord.com/api/oauth2/token",
        access_token_params=None,
        api_base_url="https://discord.com/api/v10/",
        client_kwargs={"scope": "identify"},
    )
else:
    print(
        "WARNING: Discord OAuth2 not configured. Set DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET in .env"
    )


# In-memory user storage (for MVP - consider database for production)
user_sessions: dict[str, dict] = {}


def create_session(user_data: dict) -> str:
    """Create a secure session token for the user.

    Args:
        user_data: Dictionary containing user information (id, username, avatar).

    Returns:
        Signed session token string.
    """
    session_id = secrets.token_urlsafe(32)
    user_sessions[session_id] = {
        "user": user_data,
        "created_at": datetime.now().isoformat(),
    }
    return serializer.dumps(session_id)


def get_session_from_cookie(session_cookie: Optional[str]) -> Optional[dict]:
    """Validate and retrieve session data from signed cookie.

    Args:
        session_cookie: Signed session cookie value.

    Returns:
        User session data if valid, None otherwise.
    """
    if not session_cookie:
        return None

    try:
        session_id = serializer.loads(session_cookie, max_age=SESSION_MAX_AGE)
        return user_sessions.get(session_id)
    except (BadSignature, SignatureExpired):
        return None


def delete_session(session_cookie: Optional[str]) -> None:
    """Delete a user session.

    Args:
        session_cookie: Signed session cookie value to delete.
    """
    if not session_cookie:
        return

    try:
        session_id = serializer.loads(session_cookie, max_age=SESSION_MAX_AGE)
        if session_id in user_sessions:
            del user_sessions[session_id]
    except (BadSignature, SignatureExpired):
        pass


@router.get("/login")
async def login(request: Request):
    """Initiate Discord OAuth2 login flow.

    Redirects user to Discord authorization page.

    Returns:
        RedirectResponse to Discord OAuth2 authorization URL.

    Raises:
        HTTPException: If Discord OAuth2 is not configured.
    """
    if not DISCORD_CLIENT_ID or not DISCORD_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Discord OAuth2 not configured. Please set DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET.",
        )

    redirect_uri = DISCORD_REDIRECT_URI
    return await oauth.discord.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def auth_callback(request: Request):
    """Handle Discord OAuth2 callback.

    Exchanges authorization code for access token and retrieves user information.
    Creates a secure session and sets a signed cookie.

    Returns:
        RedirectResponse to home page with session cookie set.

    Raises:
        HTTPException: If OAuth2 exchange fails or user info cannot be retrieved.
    """
    try:
        # Exchange authorization code for access token
        token = await oauth.discord.authorize_access_token(request)

        # Fetch user information from Discord API
        resp = await oauth.discord.get("users/@me", token=token)
        user_info = resp.json()

        # Extract relevant user data
        user_data = {
            "id": user_info["id"],
            "username": user_info["username"],
            "discriminator": user_info.get("discriminator", "0"),
            "avatar": user_info.get("avatar"),
            "global_name": user_info.get("global_name"),
        }

        # Create session
        session_token = create_session(user_data)

        # Create response with redirect to home
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key=COOKIE_NAME,
            value=session_token,
            max_age=SESSION_MAX_AGE,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax",
        )

        return response

    except Exception as e:
        print(f"OAuth callback error: {e}")
        raise HTTPException(status_code=400, detail="Authentication failed")


@router.post("/logout")
async def logout(session: Optional[str] = Cookie(None, alias=COOKIE_NAME)):
    """Log out the current user.

    Deletes the user session and clears the session cookie.

    Args:
        session: Session cookie value.

    Returns:
        JSONResponse with success message and cleared cookie.
    """
    delete_session(session)

    response = JSONResponse({"success": True, "message": "Logged out successfully"})
    response.delete_cookie(key=COOKIE_NAME)

    return response


@router.get("/me")
async def get_current_user(session: Optional[str] = Cookie(None, alias=COOKIE_NAME)):
    """Get current authenticated user information.

    Args:
        session: Session cookie value.

    Returns:
        JSON with user data if authenticated, or null user if not.
    """
    session_data = get_session_from_cookie(session)

    if session_data:
        return {"authenticated": True, "user": session_data["user"]}

    return {"authenticated": False, "user": None}
