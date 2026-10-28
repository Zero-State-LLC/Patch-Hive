"""
Pydantic schemas for Community API (users, auth, votes, comments).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, model_validator


# User schemas
class UserBase(BaseModel):
    """Base schema for user data."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    display_name: Optional[str] = Field(default=None, max_length=100)
    avatar_url: Optional[str] = None
    allow_public_avatar: bool = True
    bio: Optional[str] = None


class UserCreate(UserBase):
    """Schema for user registration."""

    password: str = Field(..., min_length=8, max_length=128)
    referral_code: Optional[str] = Field(
        default=None, description="Optional code from a referrer during signup."
    )


class UserUpdate(BaseModel):
    """Schema for updating user profile."""

    display_name: Optional[str] = Field(default=None, max_length=100)
    avatar_url: Optional[str] = None
    allow_public_avatar: Optional[bool] = None
    bio: Optional[str] = None


class UserResponse(UserBase):
    """Schema for user response."""

    id: int
    referral_code: str
    referred_by: Optional[int] = None
    role: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PublicUserResponse(BaseModel):
    """A user as anyone else sees them: no email, referral code or role."""

    id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def _hide_private_avatar(cls, data):
        if not isinstance(data, dict) and getattr(data, "allow_public_avatar", True) is False:
            return {
                "id": data.id,
                "username": data.username,
                "display_name": data.display_name,
                "avatar_url": None,
                "bio": data.bio,
                "created_at": data.created_at,
            }
        return data


# Auth schemas
class LoginRequest(BaseModel):
    """Schema for login request."""

    username: str
    password: str = Field(..., max_length=128)


class TokenResponse(BaseModel):
    """Schema for auth token response."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# Vote schemas
class VoteCreate(BaseModel):
    """Schema for creating a vote."""

    rack_id: Optional[int] = None
    patch_id: Optional[int] = None


class VoteResponse(BaseModel):
    """Schema for vote response."""

    id: int
    user_id: int
    rack_id: Optional[int]
    patch_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# Comment schemas
class CommentBase(BaseModel):
    """Base schema for comment data."""

    content: str = Field(..., min_length=1, max_length=2000)


class CommentCreate(CommentBase):
    """Schema for creating a comment."""

    rack_id: Optional[int] = None
    patch_id: Optional[int] = None


class CommentUpdate(BaseModel):
    """Schema for updating a comment."""

    content: str = Field(..., min_length=1, max_length=2000)


class CommentResponse(CommentBase):
    """Schema for comment response."""

    id: int
    user_id: int
    rack_id: Optional[int]
    patch_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    user: Optional[PublicUserResponse] = None

    class Config:
        from_attributes = True


# Feed schemas
class FeedItem(BaseModel):
    """Schema for a feed item (rack or patch)."""

    type: str  # "rack" or "patch"
    id: int
    name: str
    description: Optional[str]
    user: PublicUserResponse
    vote_count: int
    created_at: datetime


class FeedResponse(BaseModel):
    """Schema for feed response."""

    total: int
    items: list[FeedItem]
