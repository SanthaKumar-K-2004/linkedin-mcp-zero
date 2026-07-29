from __future__ import annotations

import math
import secrets
import time
from collections import defaultdict
from typing import Any

import structlog

logger = structlog.get_logger()

# Paths that must stay reachable without an API key: container/load-balancer
# health probes and RFC 9728 protected-resource discovery are meaningless
# behind authentication.
PUBLIC_PATHS = frozenset({"/health"})
PUBLIC_PATH_PREFIXES = ("/.well-known/",)


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

            # Public health/discovery endpoints bypass auth and rate limiting.
            path = str(scope.get("path", ""))
            if path in PUBLIC_PATHS or path.startswith(PUBLIC_PATH_PREFIXES):
                await self.app(scope, receive, send)
                return

            # 1. API Key Auth
            headers = dict(scope.get("headers", []))
            client_key = headers.get(b"x-api-key", b"").decode("utf-8")
            if not client_key and b"authorization" in headers:
                auth_val = headers[b"authorization"].decode("utf-8")
                if auth_val.startswith("Bearer "):
                    client_key = auth_val[7:]

            # Constant-time comparison: a plain != leaks key length/content
            # through response timing.
            if not client_key or not secrets.compare_digest(client_key, self.api_key):
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

            # Periodic cleanup of stale client IPs to prevent memory leaks
            if len(self.requests) > 1000:
                self.requests = defaultdict(
                    list,
                    {ip: times for ip, times in self.requests.items() if times},
                )

            if len(self.requests[client_ip]) >= self.rate_limit:
                logger.warning(
                    "Rate limit exceeded",
                    client_ip=client_ip,
                    path=scope.get("path"),
                    method=method,
                )
                # Seconds until the oldest request in this client's sliding
                # window expires — clients deserve a real Retry-After hint.
                oldest = self.requests[client_ip][0]
                retry_after = max(1, math.ceil(60 - (now - oldest)))
                await send(
                    {
                        "type": "http.response.start",
                        "status": 429,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"retry-after", str(retry_after).encode()),
                        ],
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
