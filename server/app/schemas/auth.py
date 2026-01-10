"""Authentication schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request to register a new organization and user."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    organization_name: str = Field(..., min_length=1, max_length=255)


class LoginRequest(BaseModel):
    """Request to login and get access token."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Response containing access token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token expiration time in seconds")


class UserResponse(BaseModel):
    """User information response."""

    id: UUID
    email: str
    full_name: Optional[str]
    is_active: bool
    organization_id: Optional[UUID]
    organization_name: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class APIKeyCreate(BaseModel):
    """Request to create a new API key."""

    name: str = Field(..., min_length=1, max_length=255)
    scopes: List[str] = Field(default_factory=list)
    expires_in_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=365,
        description="Number of days until the key expires",
    )


class APIKeyResponse(BaseModel):
    """Response after creating an API key."""

    id: UUID
    name: str
    key: Optional[str] = Field(
        default=None,
        description="The API key (only returned on creation)",
    )
    key_prefix: str = Field(description="First few characters for identification")
    scopes: List[str]
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]

    model_config = {"from_attributes": True}
