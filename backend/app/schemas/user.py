"""User schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.constants import ROLES


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    role: str
    affiliated_org_id: str | None = None
    is_active: bool
    created_at: datetime | None = None
    last_login: datetime | None = None


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str
    affiliated_org_id: str | None = None

    @field_validator("role")
    @classmethod
    def _role_allowed(cls, value: str) -> str:
        if value not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        return value


class UserPatch(BaseModel):
    is_active: bool | None = None
    affiliated_org_id: str | None = None
