"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
import dotenv


def load_api_key() -> str:
    """Load the CoursePilot API key from environment variables."""
    if os.getenv("COURSEPILOT_TEST_MODE", "").strip().lower() != "true":
        dotenv.load_dotenv()
    api_key = os.getenv("COURSEPILOT_API_KEY")
    if api_key is None:
        raise RuntimeError("COURSEPILOT_API_KEY is required")
    if len(api_key) < 16:
        raise RuntimeError("COURSEPILOT_API_KEY must contain at least 16 characters")
    return api_key


API_KEY = load_api_key()


def _load_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _load_positive_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise RuntimeError(f"{name} must be positive")
    return parsed


COOKIE_SECURE = _load_bool("COURSEPILOT_COOKIE_SECURE", default=False)
SESSION_TTL_HOURS = _load_positive_int("COURSEPILOT_SESSION_TTL_HOURS", 12)
SESSION_COOKIE_NAME = "coursepilot_session"
ALLOWED_ORIGINS = {
    origin.strip().rstrip("/")
    for origin in os.getenv("COURSEPILOT_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
}
