"""HTTP adapter for local account registration and cookie sessions."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app.auth.contracts import AuthCredentials, AuthSessionResponse
from app.auth.repository import DuplicateUsernameError
from app.auth.service import (
    AuthRateLimitError,
    AuthService,
    InvalidCredentialsError,
    IssuedSession,
    get_auth_service,
)
from app.config import (
    ALLOWED_ORIGINS,
    COOKIE_SECURE,
    SESSION_COOKIE_NAME,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is None:
        return
    allowed = ALLOWED_ORIGINS or {str(request.base_url).rstrip("/")}
    if origin.rstrip("/") not in allowed:
        raise HTTPException(status_code=403, detail="Cross-origin request rejected")


def _session_body(session: IssuedSession) -> dict[str, object]:
    return AuthSessionResponse(
        user=session.user,
        csrf_token=session.csrf_token,
    ).model_dump(mode="json")


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        path="/",
    )


def _raise_rate_limit(exc: AuthRateLimitError) -> None:
    raise HTTPException(
        status_code=429,
        detail="Too many authentication attempts",
        headers={"Retry-After": str(exc.retry_after)},
    ) from exc


@router.post("/register", status_code=201)
def register(
    credentials: AuthCredentials,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> JSONResponse:
    _require_same_origin(request)
    try:
        session = auth.register(
            username=credentials.username,
            password=credentials.password,
            client_key=_client_key(request),
        )
    except DuplicateUsernameError as exc:
        raise HTTPException(status_code=409, detail="Username is unavailable") from exc
    except AuthRateLimitError as exc:
        _raise_rate_limit(exc)

    response = JSONResponse(
        status_code=201,
        content=_session_body(session),
        headers={"Cache-Control": "no-store"},
    )
    _set_session_cookie(response, session.token)
    return response


@router.post("/login")
def login(
    credentials: AuthCredentials,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> JSONResponse:
    _require_same_origin(request)
    try:
        session = auth.login(
            username=credentials.username,
            password=credentials.password,
            client_key=_client_key(request),
        )
    except (InvalidCredentialsError, ValueError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        ) from exc
    except AuthRateLimitError as exc:
        _raise_rate_limit(exc)

    response = JSONResponse(
        content=_session_body(session),
        headers={"Cache-Control": "no-store"},
    )
    _set_session_cookie(response, session.token)
    return response


def _require_session(
    token: str | None,
    auth: AuthService,
) -> IssuedSession:
    session = auth.authenticate(token) if token else None
    if session is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return session


@router.get("/me")
def me(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    auth: AuthService = Depends(get_auth_service),
) -> JSONResponse:
    session = _require_session(session_token, auth)
    return JSONResponse(
        content=_session_body(session),
        headers={"Cache-Control": "no-store"},
    )


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    auth: AuthService = Depends(get_auth_service),
) -> Response:
    _require_same_origin(request)
    session = _require_session(session_token, auth)
    if not secrets.compare_digest(session.csrf_token, csrf_token or ""):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    auth.logout(session.token)
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )
    return response
