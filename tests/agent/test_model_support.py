from __future__ import annotations

from app.agent.model_support import load_optional_model


def test_test_mode_never_enables_external_model_from_ambient_key(monkeypatch) -> None:
    monkeypatch.setenv("COURSEPILOT_TEST_MODE", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ambient-secret-must-not-be-used")
    load_optional_model.cache_clear()
    try:
        assert load_optional_model() is None
    finally:
        load_optional_model.cache_clear()
