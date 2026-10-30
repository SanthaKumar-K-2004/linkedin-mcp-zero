from __future__ import annotations

import hmac
import time
from collections import defaultdict
from typing import Any

import structlog

logger = structlog.get_logger()


class APIKeyAndRateLimitMiddleware:
    """ASGI middleware for API Key authentication and client IP-based rate limiting."""

    MAX_FAILED_AUTH_PER_MINUTE = 10

    def __init__(
        self,
        app: Any,
        api_key: str | None,
        rate_limit_per_minute: int = 60,
        require_api_key: bool = True,
    ) -> None:
        self.app = app
        self.api_key = api_key or ""
        # When OAuth already authenticated the request, only rate limiting is applied here.
        self.require_api_key = require_api_key
        if require_api_key and not self.api_key:
            raise ValueError("API key authentication requires a non-empty api_key")
        self.rate_limit = rate_limit_per_minute
        self.requests: dict[str, list[float]] = defaultdict(list)
        self.failed_auth: dict[str, list[float]] = defaultdict(list)

    @staticmethod
    def _decode(value: bytes) -> str:
        return value.decode("utf-8", errors="replace")

    def _key_matches(self, supplied: str) -> bool:
        # Constant-time comparison: plain != leaks the matching prefix length through timing.
        return bool(supplied) and hmac.compare_digest(supplied.encode("utf-8"), self.api_key.encode("utf-8"))

    async def _reject(self, send: Any, status: int, body: bytes, retry_after: int | None = None) -> None:
        headers = [(b"content-type", b"application/json")]
        if retry_after is not None:
            headers.append((b"retry-after", str(retry_after).encode()))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            method = scope.get("method", "GET")
            path = scope.get("path", "")
            # Fast-path OPTIONS requests (CORS preflight is handled by CORSMiddleware)
            if method == "OPTIONS":
                await self.app(scope, receive, send)
                return

            # Public unauthenticated routes: root status, health checks & OAuth discovery
            if path in {"/", "/health", "/healthz", "/ping"} or path.startswith("/.well-known/"):
                await self.app(scope, receive, send)
                return

            client = scope.get("client")
            client_ip = client[0] if client else "unknown"
            now = time.time()

            # 0. Throttle brute-force attempts BEFORE checking the key.
            self.failed_auth[client_ip] = [t for t in self.failed_auth[client_ip] if now - t < 60]
            if len(self.failed_auth[client_ip]) >= self.MAX_FAILED_AUTH_PER_MINUTE:
                logger.warning("Too many failed auth attempts", client_ip=client_ip)
                await self._reject(send, 429, b'{"error": "Too Many Requests"}', retry_after=60)
                return

            # 1. API Key Auth (skipped when OAuth middleware is the authenticator)
            if self.require_api_key:
                headers = dict(scope.get("headers", []))
                client_key = self._decode(headers.get(b"x-api-key", b""))
                if not client_key and b"authorization" in headers:
                    auth_val = self._decode(headers[b"authorization"])
                    if auth_val.startswith("Bearer "):
                        client_key = auth_val[7:]

                if not self._key_matches(client_key):
                    self.failed_auth[client_ip].append(now)
                    logger.warning("Unauthorized request blocked", path=path, method=method)
                    await self._reject(
                        send,
                        401,
                        b'{"error": "Unauthorized", "detail": "Invalid or missing API key"}',
                    )
                    return

            # 2. Rate Limiting
            self.requests[client_ip] = [t for t in self.requests[client_ip] if now - t < 60]

            # Periodic cleanup of stale client IPs to prevent memory leaks
            if len(self.requests) > 1000:
                self.requests = defaultdict(
                    list,
                    {ip: valid for ip, times in self.requests.items() if (valid := [t for t in times if now - t < 60])},
                )

            if len(self.requests[client_ip]) >= self.rate_limit:
                logger.warning(
                    "Rate limit exceeded",
                    client_ip=client_ip,
                    path=scope.get("path"),
                    method=method,
                )
                await self._reject(send, 429, b'{"error": "Too Many Requests", "detail": "Rate limit exceeded"}', 60)
                return

            self.requests[client_ip].append(now)

        await self.app(scope, receive, send)
