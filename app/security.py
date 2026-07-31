"""Bearer-token authentication."""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException

from app.config import API_KEY


async def require_bearer_token(
    authorization: str | None = Header(default=None),
) -> None:
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    scheme, separator, credential = authorization.partition(" ")
    if separator != " " or scheme != "Bearer" or not credential:
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    if not secrets.compare_digest(credential, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
