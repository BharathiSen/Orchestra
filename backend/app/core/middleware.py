"""ASGI middleware for transport-level concerns.

Kept out of ``main.py`` so the app factory stays a wiring file.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class SelectiveGZipMiddleware(GZipMiddleware):
    """GZip everything except paths that stream.

    Compressing ``text/event-stream`` is actively harmful: the compressor holds
    bytes back waiting for a worthwhile block, which is indistinguishable from a
    hung request to someone watching a chat reply appear. Small JSON responses
    are where compression pays, so the streaming routes opt out entirely.
    """

    def __init__(self, app: ASGIApp, *, exclude_paths: Iterable[str], **kwargs) -> None:
        super().__init__(app, **kwargs)
        self.exclude_paths = tuple(exclude_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path", "").startswith(self.exclude_paths):
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)


class SecurityHeadersMiddleware:
    """Attach hardening headers to every HTTP response.

    Implemented at the ASGI layer and applied only to the
    ``http.response.start`` message, so streamed bodies are untouched — the
    headers are already flushed before the first SSE chunk is written.

    The CSP here is deliberately strict because this app serves JSON and
    event-streams only: no scripts, styles, or images originate from it. The
    browser-facing CSP that has to accommodate Next.js lives in the frontend's
    own header config.
    """

    CSP = (
        "default-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "form-action 'none'"
    )

    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        self.app = app
        # Only advertise HSTS where TLS actually terminates. Sending it over
        # plain HTTP in local development would pin localhost to https.
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                already_set = {name.lower() for name, _ in headers}
                for name, value in self._headers():
                    key = name.lower().encode()
                    if key not in already_set:
                        headers.append((name.encode(), value.encode()))
            await send(message)

        await self.app(scope, receive, send_with_headers)

    def _headers(self) -> list[tuple[str, str]]:
        headers = [
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("Referrer-Policy", "strict-origin-when-cross-origin"),
            ("Permissions-Policy", "camera=(), microphone=(), geolocation=(), interest-cohort=()"),
            ("Content-Security-Policy", self.CSP),
            ("Cross-Origin-Opener-Policy", "same-origin"),
        ]
        if self.hsts:
            headers.append(
                ("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
            )
        return headers


class MaxBodySizeMiddleware:
    """Reject request bodies larger than ``max_bytes``.

    ``Content-Length`` is checked first so an oversized upload is refused before
    a single byte is read. That header is advisory and absent on chunked
    requests, so the body is also counted as it streams in and the connection is
    failed the moment the limit is crossed.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.max_bytes <= 0:
            await self.app(scope, receive, send)
            return

        declared = self._content_length(scope)
        if declared is not None and declared > self.max_bytes:
            await self._reject(send, declared)
            return

        received = 0
        too_large = False

        async def counting_receive() -> Message:
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    too_large = True
                    # Ending the stream stops the handler from waiting on a body
                    # we have already decided to refuse.
                    return {"type": "http.disconnect"}
            return message

        wrapped_send_started = False

        async def guarded_send(message: Message) -> None:
            nonlocal wrapped_send_started
            if message["type"] == "http.response.start":
                wrapped_send_started = True
            await send(message)

        await self.app(scope, counting_receive, guarded_send)

        if too_large and not wrapped_send_started:
            await self._reject(send, received)

    @staticmethod
    def _content_length(scope: Scope) -> int | None:
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    return int(value)
                except ValueError:
                    return None
        return None

    async def _reject(self, send: Send, size: int) -> None:
        logger.warning("Rejected request body of %s bytes (limit %s)", size, self.max_bytes)
        body = (
            b'{"detail":"Request body too large. Limit is '
            + str(self.max_bytes).encode()
            + b' bytes."}'
        )
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
