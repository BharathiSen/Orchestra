import json
import uuid
from collections.abc import Iterator
from typing import Any

import google.generativeai as genai
from fastapi import HTTPException, status
from google.api_core import exceptions as google_exceptions

from app.core.config import settings
from app.services.llm_types import ChatCompletionResult, ToolCallRequest

SUPPORTED_MODELS = [
    {
        "id": "gemini-2.0-flash",
        "label": "Gemini 2.0 Flash",
        "description": "Fast default model for Orchestra chat",
    },
    {
        "id": "gemini-2.0-flash-lite",
        "label": "Gemini 2.0 Flash Lite",
        "description": "Cheaper/faster for simple questions",
    },
    {
        "id": "gemini-1.5-flash",
        "label": "Gemini 1.5 Flash",
        "description": "Often has separate free-tier quota from 2.0",
    },
    {
        "id": "gemini-1.5-pro",
        "label": "Gemini 1.5 Pro",
        "description": "Stronger reasoning for harder prompts",
    },
]


def _openai_tools_to_gemini(tools: list[dict[str, Any]] | None) -> list[Any] | None:
    if not tools:
        return None
    declarations = []
    for tool in tools:
        fn = tool.get("function") or {}
        name = fn.get("name")
        if not name:
            continue
        # High-level FunctionDeclaration accepts a JSON-schema-like dict.
        declarations.append(
            genai.types.FunctionDeclaration(
                name=name,
                description=fn.get("description") or "",
                parameters=fn.get("parameters") or {"type": "object", "properties": {}},
            )
        )
    if not declarations:
        return None
    return [genai.types.Tool(function_declarations=declarations)]


class GeminiService:
    """Google Gemini chat wrapper with streaming + function calling."""

    def __init__(self) -> None:
        if not settings.gemini_configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Gemini API key is not configured. "
                    "Set GEMINI_API_KEY in your .env and restart the backend."
                ),
            )
        genai.configure(api_key=settings.gemini_api_key)

    def _split_messages(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]]]:
        system_instruction = settings.default_system_prompt
        contents: list[dict[str, Any]] = []

        for message in messages:
            role = message.get("role", "")
            if role == "system":
                content = (message.get("content") or "").strip()
                if content:
                    system_instruction = content
                continue

            if role == "tool":
                # Gemini expects function responses as user-role function_response parts.
                name = message.get("name") or "tool"
                raw = message.get("content") or ""
                contents.append(
                    {
                        "role": "user",
                        "parts": [
                            genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=name,
                                    response={"result": raw},
                                )
                            )
                        ],
                    }
                )
                continue

            if role == "assistant":
                tool_calls = message.get("tool_calls") or []
                if tool_calls:
                    parts = []
                    for tc in tool_calls:
                        fn = tc.get("function") or {}
                        args_raw = fn.get("arguments") or "{}"
                        try:
                            args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                        except json.JSONDecodeError:
                            args = {"raw": args_raw}
                        parts.append(
                            genai.protos.Part(
                                function_call=genai.protos.FunctionCall(
                                    name=fn.get("name") or "",
                                    args=args if isinstance(args, dict) else {"value": args},
                                )
                            )
                        )
                    contents.append({"role": "model", "parts": parts})
                    continue

                text = (message.get("content") or "").strip()
                if text:
                    contents.append({"role": "model", "parts": [text]})
                continue

            if role == "user":
                text = (message.get("content") or "").strip()
                if text:
                    contents.append({"role": "user", "parts": [text]})

        return system_instruction, contents

    def complete_chat(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = "auto",
    ) -> ChatCompletionResult:
        system_instruction, contents = self._split_messages(messages)
        if not contents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No user messages to send to Gemini.",
            )

        gemini_tools = _openai_tools_to_gemini(tools)
        try:
            generative_model = genai.GenerativeModel(
                model_name=model,
                system_instruction=system_instruction,
                tools=gemini_tools,
                generation_config={"temperature": temperature},
            )
            response = generative_model.generate_content(contents)
        except Exception as exc:  # noqa: BLE001
            self._raise_mapped(exc)

        return self._parse_response(response)

    def stream_chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        tools: list[dict[str, Any]] | None = None,
        # Accepted for interface parity with OpenAICompatibleService and left
        # unfilled: this adapter does not read Gemini's usageMetadata yet, so
        # streamed turns on Gemini keep the token estimate.
        usage_sink: dict[str, int] | None = None,
    ) -> Iterator[str]:
        system_instruction, contents = self._split_messages(messages)
        if not contents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No user messages to send to Gemini.",
            )
        if contents[-1].get("role") != "user" and not any(
            hasattr(p, "function_response") for p in (contents[-1].get("parts") or [])
        ):
            # Soft check — Gemini needs a user turn; function responses count as user.
            pass

        try:
            generative_model = genai.GenerativeModel(
                model_name=model,
                system_instruction=system_instruction,
                generation_config={"temperature": temperature},
            )
            stream = generative_model.generate_content(contents, stream=True)
            for chunk in stream:
                try:
                    text = chunk.text
                except Exception:  # noqa: BLE001 — empty/partial chunks
                    continue
                if text:
                    yield text
        except Exception as exc:  # noqa: BLE001
            self._raise_mapped(exc)

    def _parse_response(self, response: Any) -> ChatCompletionResult:
        tool_calls: list[ToolCallRequest] = []
        text_parts: list[str] = []
        raw_tool_calls: list[dict[str, Any]] = []

        try:
            candidates = response.candidates or []
        except Exception:  # noqa: BLE001
            candidates = []

        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                fc = getattr(part, "function_call", None)
                if fc and getattr(fc, "name", None):
                    # Convert protobuf MapComposite / dict-like args to JSON.
                    args_obj = dict(fc.args) if fc.args else {}
                    args_json = json.dumps(args_obj)
                    call_id = f"call_{uuid.uuid4().hex[:12]}"
                    tool_calls.append(
                        ToolCallRequest(id=call_id, name=fc.name, arguments=args_json)
                    )
                    raw_tool_calls.append(
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {"name": fc.name, "arguments": args_json},
                        }
                    )
                else:
                    text = getattr(part, "text", None)
                    if text:
                        text_parts.append(text)

        content = "".join(text_parts) if text_parts else None
        raw_message: dict[str, Any] = {"role": "assistant", "content": content}
        if raw_tool_calls:
            raw_message["tool_calls"] = raw_tool_calls

        return ChatCompletionResult(
            content=content,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
            raw_assistant_message=raw_message,
            prompt_tokens=_gemini_usage(response, "prompt_token_count"),
            completion_tokens=_gemini_usage(response, "candidates_token_count"),
            total_tokens=_gemini_usage(response, "total_token_count"),
        )

    def _raise_mapped(self, exc: Exception) -> None:
        if isinstance(exc, HTTPException):
            raise exc
        if isinstance(exc, google_exceptions.InvalidArgument):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Gemini rejected the request: {exc}",
            ) from exc
        if isinstance(exc, google_exceptions.PermissionDenied):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Gemini API key. Check GEMINI_API_KEY.",
            ) from exc
        if isinstance(exc, google_exceptions.ResourceExhausted):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Gemini quota/rate limit hit. "
                    f"{exc} "
                    "Check https://aistudio.google.com/ and your Google AI Studio quotas."
                ),
            ) from exc

        message = str(exc)
        lowered = message.lower()
        if "api key" in lowered or "permission" in lowered or "401" in lowered:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Gemini API key. Check GEMINI_API_KEY.",
            ) from exc
        if "429" in lowered or "quota" in lowered or "resource exhausted" in lowered:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Gemini quota/rate limit: {message}",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini API error: {message}",
        ) from exc


def _gemini_usage(response: Any, attr: str) -> int | None:
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return None
    value = getattr(meta, attr, None)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
