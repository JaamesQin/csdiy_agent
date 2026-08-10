"""Password verification, sessions, CSRF binding, and endpoint throttling."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.auth.contracts import PublicUser, USERNAME_PATTERN
from app.auth.rate_limit import AttemptLimiter
from app.auth.repository import (
    DuplicateUsernameError,
    SQLiteAuthRepository,
    UserRecord,
)
from app.config import API_KEY, SESSION_TTL_HOURS
from app.storage.database import get_database


class InvalidCredentialsError(ValueError):
    pass


class AuthRateLimitError(RuntimeError):
    def __init__(self, retry_after: int) -> None:
        super().__init__("Too many authentication attempts")
        self.retry_after = retry_after


@dataclass(frozen=True)
class IssuedSession:
    token: str
    user: PublicUser
    csrf_token: str


class AuthService:
    def __init__(
        self,
        repository: SQLiteAuthRepository,
        *,
        secret: str = API_KEY,
        session_ttl_hours: int = SESSION_TTL_HOURS,
        limiter: AttemptLimiter | None = None,
    ) -> None:
        self.repository = repository
        self.secret = secret.encode("utf-8")
        self.session_ttl = timedelta(hours=session_ttl_hours)
        self.limiter = limiter or AttemptLimiter()
        self.password_hasher = PasswordHasher(
            time_cost=2,
            memory_cost=19456,
            parallelism=1,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )
        self._dummy_hash = self.password_hasher.hash(
            secrets.token_urlsafe(24)
        )

    @staticmethod
    def normalize_username(username: str) -> str:
        normalized = username.strip().casefold()
        if not USERNAME_PATTERN.fullmatch(username.strip()):
            raise ValueError("Invalid username")
        return normalized

    def register(
        self, *, username: str, password: str, client_key: str
    ) -> IssuedSession:
        rate_key = f"register:{client_key}"
        self._enforce_limit(rate_key, limit=10, window_seconds=3600)
        self.limiter.record(rate_key)
        normalized = self.normalize_username(username)
        self._validate_password(password)
        password_hash = self.password_hasher.hash(password)
        user = self.repository.create_user(
            username=username.strip(),
            username_normalized=normalized,
            password_hash=password_hash,
        )
        return self._issue_session(user)

    def login(
        self, *, username: str, password: str, client_key: str
    ) -> IssuedSession:
        normalized = self.normalize_username(username)
        self._validate_password(password)
        pair_key = f"login:{client_key}:{normalized}"
        ip_key = f"login-ip:{client_key}"
        self._enforce_limit(pair_key, limit=5, window_seconds=900)
        self._enforce_limit(ip_key, limit=30, window_seconds=900)

        user = self.repository.get_user_by_normalized(normalized)
        candidate_hash = user.password_hash if user is not None else self._dummy_hash
        verified = False
        try:
            verified = self.password_hasher.verify(candidate_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            verified = False

        if not verified or user is None or user.disabled_at is not None:
            self.limiter.record(pair_key)
            self.limiter.record(ip_key)
            raise InvalidCredentialsError("Invalid username or password")

        self.limiter.clear(pair_key)
        if self.password_hasher.check_needs_rehash(user.password_hash):
            new_hash = self.password_hasher.hash(password)
            self.repository.update_password_hash(user.id, new_hash)
            user = self.repository.get_user_by_normalized(normalized) or user
        return self._issue_session(user)

    def authenticate(self, token: str) -> IssuedSession | None:
        token_hash = self._token_hash(token)
        session = self.repository.get_active_session(token_hash)
        if session is None:
            return None
        return IssuedSession(
            token=token,
            user=self._public_user(session.user),
            csrf_token=self.csrf_token(token),
        )

    def logout(self, token: str) -> None:
        self.repository.revoke_session(self._token_hash(token))

    def csrf_token(self, token: str) -> str:
        return hmac.new(
            self.secret,
            b"coursepilot-csrf:" + token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def valid_csrf(self, token: str, supplied: str | None) -> bool:
        if not supplied:
            return False
        return secrets.compare_digest(self.csrf_token(token), supplied)

    def _issue_session(self, user: UserRecord) -> IssuedSession:
        token = secrets.token_urlsafe(32)
        self.repository.create_session(
            user=user,
            token_hash=self._token_hash(token),
            expires_at=datetime.now(UTC) + self.session_ttl,
        )
        return IssuedSession(
            token=token,
            user=self._public_user(user),
            csrf_token=self.csrf_token(token),
        )

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_password(password: str) -> None:
        if not 12 <= len(password) <= 128:
            raise ValueError("Invalid password length")

    @staticmethod
    def _public_user(user: UserRecord) -> PublicUser:
        return PublicUser(
            id=user.id,
            username=user.username,
            created_at=user.created_at,
        )

    def _enforce_limit(self, key: str, *, limit: int, window_seconds: int) -> None:
        retry_after = self.limiter.retry_after(
            key,
            limit=limit,
            window_seconds=window_seconds,
        )
        if retry_after:
            raise AuthRateLimitError(retry_after)


@lru_cache(maxsize=1)
def get_auth_service() -> AuthService:
    return AuthService(SQLiteAuthRepository(get_database()))


__all__ = [
    "AuthRateLimitError",
    "AuthService",
    "DuplicateUsernameError",
    "InvalidCredentialsError",
    "IssuedSession",
    "get_auth_service",
]
