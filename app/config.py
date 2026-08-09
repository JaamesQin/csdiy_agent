"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
import dotenv


def load_api_key() -> str:
    """Load the CoursePilot API key from environment variables."""
    dotenv.load_dotenv()
    api_key = os.getenv("COURSEPILOT_API_KEY")
    # api_key = os.getenv("COURSEPILOT_API_KEY")
    if api_key is None:
        raise RuntimeError("COURSEPILOT_API_KEY is required")
    if len(api_key) < 16:
        raise RuntimeError("COURSEPILOT_API_KEY must contain at least 16 characters")
    return api_key


API_KEY = load_api_key()
