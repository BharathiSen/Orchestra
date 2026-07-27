from collections.abc import Iterator

import google.generativeai as genai
from fastapi import HTTPException, status
from google.api_core import exceptions as google_exceptions

from app.core.config import settings

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


class GeminiService:
    """Google Gemini chat wrapper with streaming token output."""

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

    def stream_chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
    ) -> Iterator[str]:
        system_instruction = settings.default_system_prompt
        contents: list[dict] = []

        for message in messages:
            role = message.get("role", "")
            content = (message.get("content") or "").strip()
            if not content:
                continue
            if role == "system":
                system_instruction = content
                continue
            if role == "user":
                contents.append({"role": "user", "parts": [content]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [content]})

        if not contents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No user messages to send to Gemini.",
            )

        # Gemini expects the last turn to be from the user.
        if contents[-1]["role"] != "user":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conversation must end with a user message.",
            )

        try:
            generative_model = genai.GenerativeModel(
                model_name=model,
                system_instruction=system_instruction,
                generation_config={
                    "temperature": temperature,
                },
            )
            stream = generative_model.generate_content(contents, stream=True)
            for chunk in stream:
                try:
                    text = chunk.text
                except Exception:  # noqa: BLE001 — empty/partial chunks
                    continue
                if text:
                    yield text
        except google_exceptions.InvalidArgument as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Gemini rejected the request: {exc}",
            ) from exc
        except google_exceptions.PermissionDenied as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Gemini API key. Check GEMINI_API_KEY.",
            ) from exc
        except google_exceptions.ResourceExhausted as exc:
            raw = str(exc)
            detail = (
                "Gemini quota/rate limit hit. "
                f"{raw} "
                "Check https://aistudio.google.com/ and your Google AI Studio quotas."
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=detail,
            ) from exc
        except Exception as exc:  # noqa: BLE001
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
