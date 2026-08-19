"""Async structured-output client for the StudyKit generation model."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol
from urllib.parse import urlsplit

import httpx

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_REASONING_EFFORT = "high"
EMPTY_CONTENT_RETRY_SUFFIX = """\

上一传输只产生了内部推理，没有产生最终 message.content。请重新完成本轮任务：
- 保持当前思考模式；完成内部分析后必须继续写出最终答案。
- 在 message.content 中输出一个非空、完整、可解析的 JSON object。
- 第一个非空字符必须是 {，最后一个非空字符必须是 }。
- 不要输出 Markdown 围栏或 JSON 之外的文字。"""
INVALID_JSON_RETRY_SUFFIX = """\

上一传输的 message.content 不是合法 JSON。请保持当前思考模式并重新完成本轮任务：
- 输出一个非空、完整、可解析的 JSON object，不要输出 Markdown 围栏或额外文字。
- JSON 字符串中的反斜杠必须合法转义；LaTeX 命令和集合花括号前的反斜杠必须写成 JSON 所需的双反斜杠。
- 不要提交含有 \\{、\\} 等非法 JSON 转义的字符串；需要显示花括号时直接使用 { 和 }。
- 提交前确认整个 message.content 能被严格 JSON parser 解析。"""
LENGTH_RETRY_SUFFIX = """\

上一传输耗尽了输出预算，未能写完最终 JSON。请保持当前思考模式并重新完成本轮任务：
- 精简内部分析，优先预留足够预算写完最终 message.content。
- 不重复 SourceChunks、Schema 或上一轮分析；文本字段保持短而具体。
- 最终仍须输出非空、完整、严格可解析并符合 Schema 的 JSON object。
- 不要降低证据覆盖、控制继承或答案核算要求。"""


class ModelError(RuntimeError):
    """Base class for model adapter failures."""


class ModelConfigurationError(ModelError):
    """The model client configuration is missing or unsafe."""


class ModelAPIError(ModelError):
    """The remote API rejected the request or could not serve it."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ModelResponseError(ModelError):
    """The remote response did not contain a usable JSON object."""

    def __init__(
        self,
        message: str,
        *,
        model: str | None = None,
        finish_reason: str | None = None,
        usage: Mapping[str, int] | None = None,
        request_id: str | None = None,
        partial_content: str | None = None,
        transport_attempts: int = 1,
        retry_diagnostics: tuple[dict[str, Any], ...] = (),
    ) -> None:
        super().__init__(message)
        self.model = model
        self.finish_reason = finish_reason
        self.usage = dict(usage or {})
        self.request_id = request_id
        self.partial_content = partial_content
        self.transport_attempts = transport_attempts
        self.retry_diagnostics = retry_diagnostics


@dataclass(frozen=True)
class ModelResponse:
    """Validated structured model response and request metadata."""

    output: dict[str, Any]
    raw_content: str
    model: str
    finish_reason: str
    usage: dict[str, int]
    request_id: str | None = None
    transport_attempts: int = 1
    retry_diagnostics: tuple[dict[str, Any], ...] = ()


class StructuredModel(Protocol):
    """Structured model interface with per-stage controls."""

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        thinking_enabled: bool | None = None,
        max_tokens: int | None = None,
        timeout_seconds: float | None = None,
    ) -> ModelResponse:
        """Generate exactly one JSON object."""


def _chat_completions_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ModelConfigurationError("LLM base URL must not be empty")

    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ModelConfigurationError("LLM base URL must be an HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ModelConfigurationError("LLM base URL must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ModelConfigurationError(
            "LLM base URL must not contain a query string or fragment"
        )

    if parsed.path.rstrip("/").endswith("/chat/completions"):
        return normalized
    if parsed.path.rstrip("/").endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


def _parse_json_object(content: str) -> dict[str, Any]:
    candidate = content.strip()
    if candidate.startswith("```") and candidate.endswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 3 and lines[0].strip().lower() in {"```", "```json"}:
            candidate = "\n".join(lines[1:-1]).strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ModelResponseError(
            f"model response is not valid JSON: line {exc.lineno}, column {exc.colno}"
        ) from exc
    if not isinstance(parsed, dict):
        raise ModelResponseError("model response must be a JSON object")
    return parsed


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text.strip()[:500] or "empty response body"

    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                return message[:500]
        if isinstance(error, str) and error:
            return error[:500]
        detail = body.get("detail")
        if isinstance(detail, str) and detail:
            return detail[:500]
    return json.dumps(body, ensure_ascii=False)[:500]


def _retry_diagnostic(
    error: ModelResponseError, *, thinking_enabled: bool, code: str
) -> dict[str, Any]:
    """Record discarded response metadata without retaining model reasoning."""

    return {
        "code": code,
        "thinking_enabled": thinking_enabled,
        "model": error.model,
        "finish_reason": error.finish_reason,
        "usage": dict(error.usage),
        "request_id": error.request_id,
    }


def _response_retry_payload(
    payload: dict[str, Any], suffix: str
) -> dict[str, Any]:
    """Repeat the same reasoning mode with a response-specific reminder."""

    messages = [dict(message) for message in payload["messages"]]
    user_message = messages[-1]
    user_message["content"] = (
        str(user_message["content"]) + suffix
    )
    return {
        **payload,
        "messages": messages,
    }


@dataclass
class DeepSeekModel:
    """OpenAI-compatible DeepSeek V4 Flash client.

    ``base_url`` may be a host URL, a URL ending in ``/v1``, or the complete
    chat-completions endpoint. API keys are accepted only through construction
    or :meth:`from_env`; they are never included in dataclass representations.
    """

    api_key: str = field(repr=False)
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout_seconds: float = 600.0
    max_tokens: int = 65_536
    temperature: float = 0.1
    thinking_enabled: bool = False
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    max_retries: int = 4
    max_empty_content_retries: int = 5
    max_invalid_json_retries: int = 4
    max_length_retries: int = 2
    retry_base_delay_seconds: float = 1.0
    _transport: httpx.AsyncBaseTransport | None = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ModelConfigurationError("LLM API key must not be empty")
        if not self.model.strip():
            raise ModelConfigurationError("LLM model name must not be empty")
        if self.timeout_seconds <= 0:
            raise ModelConfigurationError("LLM timeout must be positive")
        if self.max_tokens <= 0:
            raise ModelConfigurationError("LLM max_tokens must be positive")
        if not 0 <= self.temperature <= 2:
            raise ModelConfigurationError("LLM temperature must be between 0 and 2")
        if self.reasoning_effort not in {"low", "high", "max"}:
            raise ModelConfigurationError(
                "LLM reasoning_effort must be low, high, or max"
            )
        if self.max_retries < 0:
            raise ModelConfigurationError("LLM max_retries must not be negative")
        if self.max_empty_content_retries < 0:
            raise ModelConfigurationError(
                "empty-content retries must not be negative"
            )
        if self.max_invalid_json_retries < 0:
            raise ModelConfigurationError(
                "invalid-JSON retries must not be negative"
            )
        if self.max_length_retries < 0:
            raise ModelConfigurationError(
                "length retries must not be negative"
            )
        if self.retry_base_delay_seconds < 0:
            raise ModelConfigurationError("LLM retry delay must not be negative")
        _chat_completions_url(self.base_url)

    @classmethod
    def from_env(cls) -> DeepSeekModel:
        """Build a client without coupling it to inbound CoursePilot auth."""

        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ModelConfigurationError("DEEPSEEK_API_KEY is required")

        return cls(
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL),
            model=os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL),
            reasoning_effort=os.getenv(
                "DEEPSEEK_REASONING_EFFORT", DEFAULT_REASONING_EFFORT
            ),
        )

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        thinking_enabled: bool | None = None,
        max_tokens: int | None = None,
        timeout_seconds: float | None = None,
    ) -> ModelResponse:
        """Request and validate one non-streaming JSON object."""

        if not system_prompt.strip():
            raise ValueError("system_prompt must not be empty")
        if not user_prompt.strip():
            raise ValueError("user_prompt must not be empty")

        effective_thinking = (
            self.thinking_enabled
            if thinking_enabled is None
            else thinking_enabled
        )
        effective_max_tokens = self.max_tokens if max_tokens is None else max_tokens
        effective_timeout = (
            self.timeout_seconds if timeout_seconds is None else timeout_seconds
        )
        if effective_max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if effective_timeout <= 0:
            raise ValueError("timeout_seconds must be positive")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "max_tokens": effective_max_tokens,
            "response_format": {"type": "json_object"},
            "thinking": {
                "type": "enabled" if effective_thinking else "disabled"
            },
        }
        if effective_thinking:
            payload["reasoning_effort"] = self.reasoning_effort
        else:
            payload["temperature"] = self.temperature
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        timeout = httpx.Timeout(effective_timeout)
        retry_diagnostics: list[dict[str, Any]] = []
        request_payload = payload
        empty_attempts = 0
        invalid_json_attempts = 0
        length_attempts = 0
        transport_attempts = 0
        async with httpx.AsyncClient(
            timeout=timeout,
            transport=self._transport,
        ) as client:
            while True:
                transport_attempts += 1
                response = await self._post_with_retries(
                    client,
                    payload=request_payload,
                    headers=headers,
                )
                try:
                    parsed = self._parse_response(response)
                except ModelResponseError as exc:
                    is_empty_content = (
                        str(exc) == "model API returned empty message content"
                    )
                    is_invalid_json = str(exc).startswith(
                        "model response is not valid JSON:"
                    )
                    is_length_limited = str(exc) == (
                        "model generation did not complete normally: length"
                    )
                    if is_empty_content and (
                        empty_attempts < self.max_empty_content_retries
                    ):
                        empty_attempts += 1
                        retry_diagnostics.append(
                            _retry_diagnostic(
                                exc,
                                thinking_enabled=(
                                    request_payload["thinking"]["type"]
                                    == "enabled"
                                ),
                                code="empty_message_content",
                            )
                        )
                        request_payload = _response_retry_payload(
                            payload, EMPTY_CONTENT_RETRY_SUFFIX
                        )
                        continue
                    if is_invalid_json and (
                        invalid_json_attempts < self.max_invalid_json_retries
                    ):
                        invalid_json_attempts += 1
                        retry_diagnostics.append(
                            _retry_diagnostic(
                                exc,
                                thinking_enabled=(
                                    request_payload["thinking"]["type"]
                                    == "enabled"
                                ),
                                code="invalid_message_json",
                            )
                        )
                        request_payload = _response_retry_payload(
                            payload, INVALID_JSON_RETRY_SUFFIX
                        )
                        continue
                    if is_length_limited and (
                        length_attempts < self.max_length_retries
                    ):
                        length_attempts += 1
                        retry_diagnostics.append(
                            _retry_diagnostic(
                                exc,
                                thinking_enabled=(
                                    request_payload["thinking"]["type"]
                                    == "enabled"
                                ),
                                code="length_limited_content",
                            )
                        )
                        request_payload = _response_retry_payload(
                            payload, LENGTH_RETRY_SUFFIX
                        )
                        continue
                    exc.transport_attempts = transport_attempts
                    exc.retry_diagnostics = tuple(retry_diagnostics)
                    raise
                return ModelResponse(
                    output=parsed.output,
                    raw_content=parsed.raw_content,
                    model=parsed.model,
                    finish_reason=parsed.finish_reason,
                    usage=parsed.usage,
                    request_id=parsed.request_id,
                    transport_attempts=transport_attempts,
                    retry_diagnostics=tuple(retry_diagnostics),
                )

        raise AssertionError("response retry loop exited unexpectedly")

    def _parse_response(self, response: httpx.Response) -> ModelResponse:
        """Parse one provider response without retaining reasoning content."""

        try:
            body = response.json()
        except ValueError as exc:
            raise ModelResponseError(
                "model API response is not valid JSON"
            ) from exc
        if not isinstance(body, dict):
            raise ModelResponseError(
                "model API response must be a JSON object"
            )

        normalized_usage: dict[str, int] = {}
        usage = body.get("usage")
        if isinstance(usage, Mapping):
            for name in (
                "prompt_tokens",
                "prompt_cache_hit_tokens",
                "prompt_cache_miss_tokens",
                "completion_tokens",
                "total_tokens",
            ):
                value = usage.get(name)
                if isinstance(value, int) and not isinstance(value, bool):
                    normalized_usage[name] = value
            completion_details = usage.get("completion_tokens_details")
            if isinstance(completion_details, Mapping):
                reasoning_tokens = completion_details.get("reasoning_tokens")
                if isinstance(reasoning_tokens, int) and not isinstance(
                    reasoning_tokens, bool
                ):
                    normalized_usage["reasoning_tokens"] = reasoning_tokens
        response_model = (
            body.get("model")
            if isinstance(body.get("model"), str)
            else self.model
        )
        request_id = (
            body.get("id") if isinstance(body.get("id"), str) else None
        )

        def response_error(
            message: str,
            finish_reason: str | None = None,
            partial_content: str | None = None,
        ) -> ModelResponseError:
            return ModelResponseError(
                message,
                model=response_model,
                finish_reason=finish_reason,
                usage=normalized_usage,
                request_id=request_id,
                partial_content=partial_content,
            )

        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise response_error("model API response has no choices")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise response_error("model API choice must be an object")

        finish_reason = choice.get("finish_reason")
        if not isinstance(finish_reason, str):
            raise response_error("model API response has no finish_reason")

        # Read only the learner-facing answer before checking finish_reason so a
        # truncated response remains diagnosable. Never retain reasoning_content.
        message = choice.get("message")
        partial_content = (
            message.get("content")
            if isinstance(message, dict)
            and isinstance(message.get("content"), str)
            else None
        )
        if finish_reason != "stop":
            raise response_error(
                f"model generation did not complete normally: {finish_reason}",
                finish_reason,
                partial_content,
            )

        if not isinstance(message, dict):
            raise response_error(
                "model API choice has no message", finish_reason
            )
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise response_error(
                "model API returned empty message content", finish_reason
            )
        try:
            output = _parse_json_object(content)
        except ModelResponseError as exc:
            raise response_error(str(exc), finish_reason, content) from exc
        return ModelResponse(
            output=output,
            raw_content=content,
            model=response_model,
            finish_reason=finish_reason,
            usage=normalized_usage,
            request_id=request_id,
        )

    async def _post_with_retries(
        self,
        client: httpx.AsyncClient,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> httpx.Response:
        endpoint = _chat_completions_url(self.base_url)
        retryable_statuses = {408, 429, 500, 502, 503, 504}

        for attempt in range(self.max_retries + 1):
            try:
                response = await client.post(endpoint, json=payload, headers=headers)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= self.max_retries:
                    raise ModelAPIError(
                        "model API request failed after retries"
                    ) from exc
                await asyncio.sleep(
                    self.retry_base_delay_seconds * (2**attempt)
                )
                continue

            if response.is_success:
                return response
            if response.status_code not in retryable_statuses:
                raise ModelAPIError(
                    f"model API returned {response.status_code}: "
                    f"{_error_message(response)}",
                    status_code=response.status_code,
                )
            if attempt >= self.max_retries:
                raise ModelAPIError(
                    f"model API returned {response.status_code} after retries: "
                    f"{_error_message(response)}",
                    status_code=response.status_code,
                )
            await asyncio.sleep(self.retry_base_delay_seconds * (2**attempt))

        raise AssertionError("retry loop exited unexpectedly")
