"""Discord OAuth integration module.

Handles Discord OAuth2 authentication flow for user login.
"""

import os
import aiohttp
from typing import Optional
from fastapi import HTTPException

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

DISCORD_API_ENDPOINT = "https://discord.com/api/v10"
DISCORD_OAUTH_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_OAUTH_TOKEN_URL = f"{DISCORD_API_ENDPOINT}/oauth2/token"
DISCORD_USER_URL = f"{DISCORD_API_ENDPOINT}/users/@me"


def get_discord_oauth_url() -> str:
    """Generate Discord OAuth authorization URL.

    Returns:
        Authorization URL for Discord OAuth.

    Raises:
        ValueError: If Discord OAuth is not configured.
    """
    if not DISCORD_CLIENT_ID or not DISCORD_REDIRECT_URI:
        raise ValueError("Discord OAuth not configured")

    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
    }

    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{DISCORD_OAUTH_AUTHORIZE_URL}?{query}"


async def exchange_code_for_token(code: str) -> dict:
    """Exchange OAuth authorization code for access token.

    Args:
        code: Authorization code from Discord OAuth callback.

    Returns:
        Token response containing access_token and other fields.

    Raises:
        HTTPException: If token exchange fails.
    """
    if not all([DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_REDIRECT_URI]):
        raise HTTPException(
            status_code=500, detail="Discord OAuth not configured"
        )

    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    async with aiohttp.ClientSession() as session:
        async with session.post(
            DISCORD_OAUTH_TOKEN_URL, data=data, headers=headers
        ) as resp:
            if resp.status != 200:
                raise HTTPException(
                    status_code=400, detail="Failed to exchange code for token"
                )
            return await resp.json()


async def get_discord_user(access_token: str) -> dict:
    """Get Discord user information using access token.

    Args:
        access_token: Discord OAuth access token.

    Returns:
        User information from Discord API.

    Raises:
        HTTPException: If user fetch fails.
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(DISCORD_USER_URL, headers=headers) as resp:
            if resp.status != 200:
                raise HTTPException(
                    status_code=400, detail="Failed to fetch Discord user"
                )
            return await resp.json()


async def authenticate_discord_user(code: str) -> tuple[str, str]:
    """Authenticate a Discord user via OAuth code.

    Args:
        code: Authorization code from Discord OAuth callback.

    Returns:
        Tuple of (discord_user_id, username).

    Raises:
        HTTPException: If authentication fails.
    """
    token_response = await exchange_code_for_token(code)
    access_token = token_response.get("access_token")

    if not access_token:
        raise HTTPException(status_code=400, detail="No access token received")

    user_data = await get_discord_user(access_token)

    discord_user_id = user_data.get("id")
    username = user_data.get("username")

    if not discord_user_id or not username:
        raise HTTPException(
            status_code=400, detail="Failed to get user information"
        )

    return discord_user_id, username


def is_discord_oauth_configured() -> bool:
    """Check if Discord OAuth is properly configured.

    Returns:
        True if all required environment variables are set.
    """
    return all([DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_REDIRECT_URI])
