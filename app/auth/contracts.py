"""Account authentication contracts."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,31}$")


class AuthCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = value.strip()
        if not USERNAME_PATTERN.fullmatch(value):
            raise ValueError(
                "Username must start with a letter or number and contain only "
                "letters, numbers, '.', '_' or '-'"
            )
        return value


class PublicUser(BaseModel):
    id: str
    username: str
    created_at: datetime


class AuthSessionResponse(BaseModel):
    user: PublicUser
    csrf_token: str
