from collections.abc import Iterator
import json

import httpx
from fastapi import HTTPException, status

from app.core.config import settings


class OpenAICompatibleService:
    """Streaming chat via OpenAI-compatible HTTP APIs (Groq, Ollama, etc.)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        provider_name: str,
        missing_key_hint: str,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.provider_name = provider_name
        self.missing_key_hint = missing_key_hint
        if not self.api_key.strip() and provider_name != "ollama":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=self.missing_key_hint,
            )

    def stream_chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
    ) -> Iterator[str]:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key.strip():
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }

        try:
            with httpx.Client(timeout=120.0) as client:
                with client.stream("POST", url, headers=headers, json=payload) as response:
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
        except HTTPException:
            raise
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
