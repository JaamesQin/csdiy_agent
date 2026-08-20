from __future__ import annotations

import json

import httpx
import pytest

from app.generation.model import (
    DeepSeekModel,
    EMPTY_CONTENT_RETRY_SUFFIX,
    INVALID_JSON_RETRY_SUFFIX,
    LENGTH_RETRY_SUFFIX,
    ModelAPIError,
    ModelConfigurationError,
    ModelResponseError,
    _chat_completions_url,
)


def _completion(content: str = '{"title": "测试 StudyKit"}') -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-test",
            "model": "deepseek-v4-flash",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "prompt_cache_hit_tokens": 8,
                "prompt_cache_miss_tokens": 2,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        },
    )


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        (
            "https://api.deepseek.com",
            "https://api.deepseek.com/v1/chat/completions",
        ),
        (
            "https://api.deepseek.com/v1/",
            "https://api.deepseek.com/v1/chat/completions",
        ),
        (
            "https://api.deepseek.com/v1/chat/completions",
            "https://api.deepseek.com/v1/chat/completions",
        ),
    ],
)
def test_chat_completions_url(base_url: str, expected: str) -> None:
    assert _chat_completions_url(base_url) == expected


def test_from_env_uses_separate_llm_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret-llm-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "provider-model-id")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

    model = DeepSeekModel.from_env()

    assert model.api_key == "secret-llm-key"
    assert model.model == "provider-model-id"
    assert model.base_url == "https://api.deepseek.com/v1"
    assert "secret-llm-key" not in repr(model)


def test_from_env_defaults_to_v4_flash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret-llm-key")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)

    model = DeepSeekModel.from_env()

    assert model.model == "deepseek-v4-flash"
    assert model.base_url == "https://api.deepseek.com"
    assert model.reasoning_effort == "high"
    assert model.max_retries == 4
    assert model.retry_base_delay_seconds == 1.0
    assert model.max_empty_content_retries == 5
    assert model.max_invalid_json_retries == 4
    assert model.max_length_retries == 2


def test_from_env_requires_llm_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(
        ModelConfigurationError, match="DEEPSEEK_API_KEY is required"
    ):
        DeepSeekModel.from_env()


def test_from_env_does_not_send_legacy_provider_key_to_official_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("COURSEPILOT_LLM_API_KEY", "legacy-secret")

    with pytest.raises(
        ModelConfigurationError, match="DEEPSEEK_API_KEY is required"
    ):
        DeepSeekModel.from_env()


async def test_generate_json_sends_openai_compatible_request() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["payload"] = json.loads(request.content)
        return _completion()

    model = DeepSeekModel(
        api_key="test-secret",
        _transport=httpx.MockTransport(handler),
    )

    response = await model.generate_json(
        system_prompt="只输出 JSON。",
        user_prompt="生成测试对象。",
    )

    assert captured["url"] == (
        "https://api.deepseek.com/v1/chat/completions"
    )
    assert captured["authorization"] == "Bearer test-secret"
    assert captured["payload"] == {
        "model": "deepseek-v4-flash",
        "messages": [
            {"role": "system", "content": "只输出 JSON。"},
            {"role": "user", "content": "生成测试对象。"},
        ],
        "stream": False,
        "temperature": 0.1,
        "max_tokens": 65_536,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }
    assert response.output == {"title": "测试 StudyKit"}
    assert response.usage["total_tokens"] == 15
    assert response.usage["prompt_cache_hit_tokens"] == 8
    assert response.usage["prompt_cache_miss_tokens"] == 2
    assert response.request_id == "chatcmpl-test"


async def test_generate_json_accepts_json_code_fence() -> None:
    model = DeepSeekModel(
        api_key="test-secret",
        _transport=httpx.MockTransport(
            lambda request: _completion('```json\n{"ok": true}\n```')
        ),
    )

    response = await model.generate_json(
        system_prompt="只输出 JSON。",
        user_prompt="生成测试对象。",
    )

    assert response.output == {"ok": True}


async def test_empty_thinking_response_retries_in_same_mode_with_reminder() -> None:
    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        if len(payloads) == 1:
            return _completion("")
        return _completion('{"ok": true}')

    model = DeepSeekModel(
        api_key="test-secret",
        _transport=httpx.MockTransport(handler),
    )

    response = await model.generate_json(
        system_prompt="只输出 JSON。",
        user_prompt="生成测试对象。",
        thinking_enabled=True,
    )

    assert response.output == {"ok": True}
    assert len(payloads) == 2
    assert payloads[0]["thinking"] == {"type": "enabled"}
    assert payloads[0]["reasoning_effort"] == "high"
    assert "temperature" not in payloads[0]
    assert payloads[1]["thinking"] == {"type": "enabled"}
    assert payloads[1]["reasoning_effort"] == "high"
    assert "temperature" not in payloads[1]
    assert payloads[1]["messages"][-1]["content"].endswith(
        EMPTY_CONTENT_RETRY_SUFFIX
    )
    assert response.transport_attempts == 2
    assert response.retry_diagnostics == (
        {
            "code": "empty_message_content",
            "thinking_enabled": True,
            "model": "deepseek-v4-flash",
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 10,
                "prompt_cache_hit_tokens": 8,
                "prompt_cache_miss_tokens": 2,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            "request_id": "chatcmpl-test",
        },
    )


async def test_empty_message_content_retry_stops_after_default_retries() -> None:
    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return _completion("")

    model = DeepSeekModel(
        api_key="test-secret",
        _transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        ModelResponseError, match="empty message content"
    ) as caught:
        await model.generate_json(
            system_prompt="只输出 JSON。",
            user_prompt="生成测试对象。",
            thinking_enabled=True,
        )

    assert len(payloads) == 6
    assert payloads[0]["thinking"] == {"type": "enabled"}
    assert all(
        payload["thinking"] == {"type": "enabled"}
        for payload in payloads[1:]
    )
    assert all(
        payload["messages"][-1]["content"].count(
            EMPTY_CONTENT_RETRY_SUFFIX
        )
        == 1
        for payload in payloads[1:]
    )
    assert caught.value.transport_attempts == 6
    assert len(caught.value.retry_diagnostics) == 5
    assert [
        item["thinking_enabled"]
        for item in caught.value.retry_diagnostics
    ] == [True, True, True, True, True]


async def test_invalid_json_retries_in_same_disabled_thinking_mode() -> None:
    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        if len(payloads) == 1:
            return _completion(r'{"activity":"$\\{t_1\\}$"}'.replace("\\\\{", "\\{"))
        return _completion('{"ok": true}')

    model = DeepSeekModel(
        api_key="test-secret",
        _transport=httpx.MockTransport(handler),
    )

    response = await model.generate_json(
        system_prompt="只输出 JSON。",
        user_prompt="生成测试对象。",
        thinking_enabled=False,
    )

    assert response.output == {"ok": True}
    assert len(payloads) == 2
    assert all(
        payload["thinking"] == {"type": "disabled"} for payload in payloads
    )
    assert payloads[1]["messages"][-1]["content"].endswith(
        INVALID_JSON_RETRY_SUFFIX
    )
    assert response.transport_attempts == 2
    assert response.retry_diagnostics[0]["code"] == "invalid_message_json"


async def test_invalid_json_retry_stops_after_configured_limit() -> None:
    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return _completion('{"bad":"\\{"}')

    model = DeepSeekModel(
        api_key="test-secret",
        max_invalid_json_retries=2,
        _transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ModelResponseError, match="not valid JSON") as caught:
        await model.generate_json(
            system_prompt="只输出 JSON。",
            user_prompt="生成测试对象。",
            thinking_enabled=True,
        )

    assert len(payloads) == 3
    assert caught.value.transport_attempts == 3
    assert [
        item["code"] for item in caught.value.retry_diagnostics
    ] == ["invalid_message_json", "invalid_message_json"]


async def test_length_response_retries_once_in_same_thinking_mode() -> None:
    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        if len(payloads) == 1:
            response = _completion('{"partial":')
            response.read()
            body = response.json()
            body["choices"][0]["finish_reason"] = "length"
            return httpx.Response(200, json=body)
        return _completion('{"ok": true}')

    model = DeepSeekModel(
        api_key="test-secret",
        _transport=httpx.MockTransport(handler),
    )

    response = await model.generate_json(
        system_prompt="只输出 JSON。",
        user_prompt="生成测试对象。",
        thinking_enabled=True,
    )

    assert response.output == {"ok": True}
    assert len(payloads) == 2
    assert all(
        payload["thinking"] == {"type": "enabled"} for payload in payloads
    )
    assert payloads[1]["messages"][-1]["content"].endswith(
        LENGTH_RETRY_SUFFIX
    )
    assert response.retry_diagnostics[0]["code"] == "length_limited_content"


async def test_length_response_stops_after_one_retry() -> None:
    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        response = _completion('{"partial":')
        response.read()
        body = response.json()
        body["choices"][0]["finish_reason"] = "length"
        return httpx.Response(200, json=body)

    model = DeepSeekModel(
        api_key="test-secret",
        max_length_retries=1,
        _transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ModelResponseError, match="normally: length") as caught:
        await model.generate_json(
            system_prompt="只输出 JSON。",
            user_prompt="生成测试对象。",
            thinking_enabled=True,
        )

    assert len(payloads) == 2
    assert caught.value.transport_attempts == 2
    assert [
        item["code"] for item in caught.value.retry_diagnostics
    ] == ["length_limited_content"]


async def test_generate_json_applies_per_call_stage_controls() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return _completion()

    model = DeepSeekModel(
        api_key="test-secret",
        _transport=httpx.MockTransport(handler),
    )

    await model.generate_json(
        system_prompt="只输出 JSON。",
        user_prompt="生成测试对象。",
        thinking_enabled=True,
        max_tokens=2048,
        timeout_seconds=600,
    )

    assert captured["thinking"] == {"type": "enabled"}
    assert captured["max_tokens"] == 2048
    assert captured["reasoning_effort"] == "high"
    assert "temperature" not in captured


async def test_generate_json_rejects_invalid_content() -> None:
    model = DeepSeekModel(
        api_key="test-secret",
        _transport=httpx.MockTransport(
            lambda request: _completion("not json")
        ),
    )

    with pytest.raises(ModelResponseError, match="not valid JSON"):
        await model.generate_json(
            system_prompt="只输出 JSON。",
            user_prompt="生成测试对象。",
        )


async def test_length_error_preserves_request_metadata() -> None:
    partial_content = '{"learning_objectives": ['
    model = DeepSeekModel(
        api_key="test-secret",
        _transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "id": "request-length",
                    "model": "deepseek-v4-flash",
                    "choices": [
                        {
                            "message": {
                                "content": partial_content,
                                "reasoning_content": "must never be retained",
                            },
                            "finish_reason": "length",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 32768,
                        "completion_tokens_details": {
                            "reasoning_tokens": 30000
                        },
                        "total_tokens": 32868,
                    },
                },
            )
        ),
    )

    with pytest.raises(ModelResponseError) as caught:
        await model.generate_json(
            system_prompt="只输出 JSON。",
            user_prompt="生成测试对象。",
        )

    assert caught.value.request_id == "request-length"
    assert caught.value.finish_reason == "length"
    assert caught.value.usage["total_tokens"] == 32868
    assert caught.value.usage["reasoning_tokens"] == 30000
    assert caught.value.partial_content == partial_content
    assert "must never be retained" not in repr(caught.value.__dict__)


async def test_non_retryable_api_error_exposes_status_not_secret() -> None:
    model = DeepSeekModel(
        api_key="do-not-leak",
        _transport=httpx.MockTransport(
            lambda request: httpx.Response(
                401,
                json={"error": {"message": "invalid credential"}},
            )
        ),
    )

    with pytest.raises(ModelAPIError) as caught:
        await model.generate_json(
            system_prompt="只输出 JSON。",
            user_prompt="生成测试对象。",
        )

    assert caught.value.status_code == 401
    assert "invalid credential" in str(caught.value)
    assert "do-not-leak" not in str(caught.value)


async def test_retryable_api_error_is_retried() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={"error": {"message": "busy"}})
        return _completion()

    model = DeepSeekModel(
        api_key="test-secret",
        max_retries=1,
        retry_base_delay_seconds=0,
        _transport=httpx.MockTransport(handler),
    )

    response = await model.generate_json(
        system_prompt="只输出 JSON。",
        user_prompt="生成测试对象。",
    )

    assert attempts == 2
    assert response.output["title"] == "测试 StudyKit"
