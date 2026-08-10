"""Account authentication and server-side sessions."""

from app.auth.service import AuthService, get_auth_service

__all__ = ["AuthService", "get_auth_service"]
