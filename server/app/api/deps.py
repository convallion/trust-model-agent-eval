"""FastAPI dependency injection."""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.security import decode_access_token, is_valid_api_key_format, verify_api_key
from app.models.user import APIKey, User

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get the current authenticated user.

    Supports both JWT tokens and API keys.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Check if it's an API key
    if is_valid_api_key_format(token):
        return await _authenticate_api_key(token, db)

    # Otherwise, treat as JWT token
    return await _authenticate_jwt(token, db)


async def _authenticate_jwt(token: str, db: AsyncSession) -> User:
    """Authenticate using JWT token."""
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(
        select(User)
        .where(User.id == UUID(user_id))
        .options(joinedload(User.organization))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


async def _authenticate_api_key(key: str, db: AsyncSession) -> User:
    """Authenticate using API key."""
    # Get all active API keys and check against hash
    result = await db.execute(
        select(APIKey)
        .where(APIKey.is_active == True)
        .options(joinedload(APIKey.user).joinedload(User.organization))
    )
    api_keys = result.scalars().all()

    for api_key in api_keys:
        if verify_api_key(key, api_key.key_hash):
            if not api_key.is_valid():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key is expired or inactive",
                )

            if not api_key.user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive",
                )

            # Update last used timestamp
            from datetime import datetime, timezone
            api_key.last_used_at = datetime.now(timezone.utc)

            return api_key.user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )


async def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current user and verify they are a superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user
