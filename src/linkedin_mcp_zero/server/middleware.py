from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

import structlog

logger = structlog.get_logger()


class APIKeyAndRateLimitMiddleware:
    """ASGI middleware for API Key authentication and client IP-based rate limiting."""

    def __init__(self, app: Any, api_key: str, rate_limit_per_minute: int = 60) -> None:
        self.app = app
        self.api_key = api_key
        self.rate_limit = rate_limit_per_minute
        self.requests: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            method = scope.get("method", "GET")
            # Fast-path OPTIONS requests (CORS preflight is handled by CORSMiddleware)
            if method == "OPTIONS":
                await self.app(scope, receive, send)
                return

            # 1. API Key Auth
            headers = dict(scope.get("headers", []))
            client_key = headers.get(b"x-api-key", b"").decode("utf-8")
            if not client_key and b"authorization" in headers:
                auth_val = headers[b"authorization"].decode("utf-8")
                if auth_val.startswith("Bearer "):
                    client_key = auth_val[7:]

            if not client_key or client_key != self.api_key:
                logger.warning(
                    "Unauthorized request blocked",
                    path=scope.get("path"),
                    method=method,
                )
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": (b'{"error": "Unauthorized", "detail": "Invalid or missing API key"}'),
                    }
                )
                return

            # 2. Rate Limiting
            client = scope.get("client")
            client_ip = client[0] if client else "unknown"
            now = time.time()
            self.requests[client_ip] = [t for t in self.requests[client_ip] if now - t < 60]

            if len(self.requests[client_ip]) >= self.rate_limit:
                logger.warning(
                    "Rate limit exceeded",
                    client_ip=client_ip,
                    path=scope.get("path"),
                    method=method,
                )
                await send(
                    {
                        "type": "http.response.start",
                        "status": 429,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": (b'{"error": "Too Many Requests", "detail": "Rate limit exceeded"}'),
                    }
                )
                return

            self.requests[client_ip].append(now)

        await self.app(scope, receive, send)
