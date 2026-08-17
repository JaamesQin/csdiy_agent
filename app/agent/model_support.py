"""Shared helpers for optional structured-model calls in the online runtime."""

from __future__ import annotations

import os
from functools import lru_cache

from app.generation.model import DeepSeekModel, ModelConfigurationError, StructuredModel


@lru_cache(maxsize=1)
def load_optional_model() -> StructuredModel | None:
    """Lazily reuse the existing DeepSeek adapter without making startup require it."""

    if os.getenv("COURSEPILOT_TEST_MODE", "").strip().lower() == "true":
        return None
    try:
        return DeepSeekModel.from_env()
    except ModelConfigurationError:
        return None


def normalized_usage(usage: dict[str, int] | None = None) -> dict[str, int]:
    usage = usage or {}
    return {
        "prompt_tokens": int(usage.get("prompt_tokens", 0)),
        "completion_tokens": int(usage.get("completion_tokens", 0)),
        "total_tokens": int(usage.get("total_tokens", 0)),
    }


def add_usage(*items: dict[str, int]) -> dict[str, int]:
    total = normalized_usage()
    for item in items:
        normalized = normalized_usage(item)
        for key in total:
            total[key] += normalized[key]
    return total
