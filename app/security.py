"""Trusted account-session and legacy API-key principals."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from enum import Enum

from fastapi import Cookie, Depends, Header, HTTPException

from app.auth.service import AuthService, get_auth_service
from app.config import API_KEY, SESSION_COOKIE_NAME


class PrincipalKind(str, Enum):
    ACCOUNT = "account"
    LEGACY_API_KEY = "legacy_api_key"


@dataclass(frozen=True)
class SecurityPrincipal:
    kind: PrincipalKind
    account_id: str | None = None
    username: str | None = None
    session_token: str | None = field(default=None, repr=False)

    def profile_user_id(self, requested_user: str | None) -> str | None:
        if self.kind is PrincipalKind.ACCOUNT:
            return f"account:{self.account_id}"
        if requested_user and requested_user.strip():
            return f"legacy:{requested_user.strip()}"
        return None


def _validate_api_key(authorization: str) -> None:
    scheme, separator, credential = authorization.partition(" ")
    if separator != " " or scheme != "Bearer" or not credential:
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    if not secrets.compare_digest(credential, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")


def require_principal(
    authorization: str | None = Header(default=None),
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    auth: AuthService = Depends(get_auth_service),
) -> SecurityPrincipal:
    if authorization is not None:
        _validate_api_key(authorization)
        return SecurityPrincipal(kind=PrincipalKind.LEGACY_API_KEY)

    if session_token:
        session = auth.authenticate(session_token)
        if session is not None:
            return SecurityPrincipal(
                kind=PrincipalKind.ACCOUNT,
                account_id=session.user.id,
                username=session.user.username,
                session_token=session_token,
            )
        raise HTTPException(status_code=401, detail="Authentication required")

    raise HTTPException(status_code=401, detail="Missing Authorization header")


async def require_bearer_token(
    authorization: str | None = Header(default=None),
) -> None:
    """Backward-compatible dependency retained for external imports."""
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    _validate_api_key(authorization)


def require_csrf(
    principal: SecurityPrincipal,
    supplied_token: str | None,
    auth: AuthService,
) -> None:
    if principal.kind is PrincipalKind.LEGACY_API_KEY:
        return
    if principal.session_token is None or not auth.valid_csrf(
        principal.session_token, supplied_token
    ):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
