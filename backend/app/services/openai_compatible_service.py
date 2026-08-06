import json
import random
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.services.llm_types import ChatCompletionResult, ToolCallRequest


class OpenAICompatibleService:
    """Streaming + tool-calling via OpenAI-compatible HTTP APIs (Groq, Ollama, etc.)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        provider_name: str,
        missing_key_hint: str,
        max_retries: int | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.provider_name = provider_name
        self.missing_key_hint = missing_key_hint
        self.max_retries = (
            settings.llm_max_retries if max_retries is None else max_retries
        )
        self.timeout_seconds = (
            settings.llm_request_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        if not self.api_key.strip() and provider_name != "ollama":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=self.missing_key_hint,
            )

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key.strip():
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _sleep_backoff(self, attempt: int) -> None:
        # Exponential backoff with jitter to ride out provider TPM limits.
        # Capped so a retry storm cannot dominate the request's wall time.
        base = min(8.0, 2**attempt)
        time.sleep(base + random.uniform(0, 0.75))

    def _timeout_error(self, exc: Exception) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=(
                f"{self.provider_name} did not respond within "
                f"{self.timeout_seconds:.0f}s. Try a shorter prompt or a faster model."
            ),
        )

    def _with_retries(self, operation: Callable[[], Any]) -> Any:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return operation()
            except HTTPException as exc:
                last_exc = exc
                if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
                    raise
                if attempt >= self.max_retries - 1:
                    raise
                self._sleep_backoff(attempt)
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code != 429:
                    raise
                if attempt >= self.max_retries - 1:
                    self._raise_http_error(exc.response.status_code, exc.response.text)
                self._sleep_backoff(attempt)
        if last_exc:
            raise last_exc
        raise RuntimeError(f"{self.provider_name} retry loop exhausted")

    def complete_chat(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = "auto",
    ) -> ChatCompletionResult:
        """Non-streaming completion — used for the tool-decision round."""
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            if tool_choice is not None:
                payload["tool_choice"] = tool_choice

        def _once() -> dict[str, Any]:
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(url, headers=self._headers(), json=payload)
                    if response.status_code >= 400:
                        self._raise_http_error(response.status_code, response.text)
                    return response.json()
            except HTTPException:
                raise
            except httpx.TimeoutException as exc:
                raise self._timeout_error(exc) from exc
            except httpx.ConnectError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        f"Cannot reach {self.provider_name} at {self.base_url}. "
                        f"{exc}"
                    ),
                ) from exc
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"{self.provider_name} API error: {exc}",
                ) from exc

        data = self._with_retries(_once)
        choices = data.get("choices") or []
        if not choices:
            return ChatCompletionResult(content="", finish_reason="stop")

        message = choices[0].get("message") or {}
        finish_reason = choices[0].get("finish_reason")
        content = message.get("content")
        tool_calls_raw = message.get("tool_calls") or []

        tool_calls: list[ToolCallRequest] = []
        for tc in tool_calls_raw:
            fn = tc.get("function") or {}
            tool_calls.append(
                ToolCallRequest(
                    id=tc.get("id") or f"call_{uuid.uuid4().hex[:12]}",
                    name=fn.get("name") or "",
                    arguments=fn.get("arguments") or "{}",
                )
            )

        usage = data.get("usage") or {}
        return ChatCompletionResult(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            raw_assistant_message=message,
            prompt_tokens=_usage_int(usage, "prompt_tokens"),
            completion_tokens=_usage_int(usage, "completion_tokens"),
            total_tokens=_usage_int(usage, "total_tokens"),
        )

    def stream_chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        tools: list[dict[str, Any]] | None = None,
    ) -> Iterator[str]:
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "none"

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                with (
                    httpx.Client(timeout=self.timeout_seconds) as client,
                    client.stream(
                        "POST", url, headers=self._headers(), json=payload
                    ) as response,
                ):
                    if response.status_code >= 400:
                        body = response.read().decode("utf-8", errors="replace")
                        self._raise_http_error(response.status_code, body)

                    for line in response.iter_lines():
                        if not line:
                            continue
                        if line.startswith("data:"):
                            data = line[5:].strip()
                        else:
                            continue
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        content = delta.get("content")
                        if content:
                            yield content
                return
            except HTTPException as exc:
                last_error = exc
                if (
                    exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS
                    or attempt >= self.max_retries - 1
                ):
                    raise
                self._sleep_backoff(attempt)
            except httpx.TimeoutException as exc:
                raise self._timeout_error(exc) from exc
            except httpx.ConnectError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        f"Cannot reach {self.provider_name} at {self.base_url}. "
                        f"{exc}"
                    ),
                ) from exc
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"{self.provider_name} API error: {exc}",
                ) from exc

        if last_error:
            raise last_error

    def _raise_http_error(self, status_code: int, body: str) -> None:
        lowered = body.lower()
        if status_code in {401, 403}:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid {self.provider_name} credentials. {body[:300]}",
            )
        if status_code == 429 or "quota" in lowered or "rate" in lowered:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"{self.provider_name} quota/rate limit: {body[:500]}",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{self.provider_name} error ({status_code}): {body[:500]}",
        )


def _usage_int(usage: dict[str, Any], key: str) -> int | None:
    value = usage.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
