"""Authentication module for Bear Map.

This module provides user authentication functionality including
password hashing, JWT token generation, and user management.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-use-env-var")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USERS_DB_PATH = os.path.join(BASE_DIR, "users.json")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


class Token(BaseModel):
    """Token response model."""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token payload model."""

    username: Optional[str] = None


class User(BaseModel):
    """User model."""

    username: str
    full_name: Optional[str] = None
    disabled: bool = False


class UserInDB(User):
    """User model with hashed password."""

    hashed_password: str


def load_users() -> dict:
    """Load users from JSON file.

    Returns:
        Dictionary of users with username as key.
    """
    if not os.path.exists(USERS_DB_PATH):
        # Create default admin user
        default_users = {
            "admin": {
                "username": "admin",
                "full_name": "Administrator",
                "hashed_password": get_password_hash("admin"),
                "disabled": False,
            }
        }
        save_users(default_users)
        return default_users

    with open(USERS_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_users(users: dict):
    """Save users to JSON file.

    Args:
        users: Dictionary of users to save.
    """
    with open(USERS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        plain_password: Plain text password.
        hashed_password: Hashed password to verify against.

    Returns:
        True if password matches, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password.

    Args:
        password: Plain text password to hash.

    Returns:
        Hashed password string.
    """
    return pwd_context.hash(password)


def get_user(username: str) -> Optional[UserInDB]:
    """Get user from database.

    Args:
        username: Username to look up.

    Returns:
        UserInDB object if found, None otherwise.
    """
    users = load_users()
    if username in users:
        user_dict = users[username]
        return UserInDB(**user_dict)
    return None


def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """Authenticate a user by username and password.

    Args:
        username: Username to authenticate.
        password: Plain text password.

    Returns:
        UserInDB object if authentication succeeds, None otherwise.
    """
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token.

    Args:
        data: Data to encode in the token.
        expires_delta: Optional expiration time delta.

    Returns:
        Encoded JWT token string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Optional[User]:
    """Get current user from JWT token.

    Args:
        token: JWT token from request.

    Returns:
        User object if token is valid, None if no token provided.

    Raises:
        HTTPException: If token is invalid.
    """
    if token is None:
        return None

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return User(**user.dict())


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user (non-disabled).

    Args:
        current_user: Current user from token.

    Returns:
        User object if active.

    Raises:
        HTTPException: If user is disabled.
    """
    if current_user and current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def create_user(username: str, password: str, full_name: Optional[str] = None) -> User:
    """Create a new user.

    Args:
        username: Username for the new user.
        password: Plain text password.
        full_name: Optional full name.

    Returns:
        Created User object.

    Raises:
        HTTPException: If username already exists.
    """
    users = load_users()
    if username in users:
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_password = get_password_hash(password)
    users[username] = {
        "username": username,
        "full_name": full_name or username,
        "hashed_password": hashed_password,
        "disabled": False,
    }
    save_users(users)
    return User(username=username, full_name=full_name, disabled=False)
