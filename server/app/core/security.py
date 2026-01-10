"""Security utilities: JWT tokens, password hashing, API keys."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ═══════════════════════════════════════════════════════════════════════════════
# Password Hashing
# ═══════════════════════════════════════════════════════════════════════════════


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password for storage."""
    return pwd_context.hash(password)


# ═══════════════════════════════════════════════════════════════════════════════
# JWT Tokens
# ═══════════════════════════════════════════════════════════════════════════════


def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload data to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """
    Decode and validate a JWT access token.

    Args:
        token: JWT token string

    Returns:
        Decoded payload or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        return payload
    except JWTError:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# API Keys
# ═══════════════════════════════════════════════════════════════════════════════


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key.

    Returns:
        Tuple of (raw_key, hashed_key)
        - raw_key: The key to give to the user (only shown once)
        - hashed_key: The hash to store in database
    """
    # Generate 32-byte random key
    random_bytes = secrets.token_urlsafe(32)
    raw_key = f"{settings.api_key_prefix}{random_bytes}"

    # Hash for storage
    hashed_key = get_password_hash(raw_key)

    return raw_key, hashed_key


def verify_api_key(raw_key: str, hashed_key: str) -> bool:
    """
    Verify an API key against its stored hash.

    Args:
        raw_key: The raw API key from the request
        hashed_key: The stored hash

    Returns:
        True if the key is valid
    """
    return verify_password(raw_key, hashed_key)


def is_valid_api_key_format(key: str) -> bool:
    """
    Check if a string looks like a valid API key format.

    Args:
        key: The key string to check

    Returns:
        True if it matches expected format
    """
    return key.startswith(settings.api_key_prefix) and len(key) > len(settings.api_key_prefix) + 20
