from __future__ import annotations

import httpx
import structlog
from typing import Any
from authlib.integrations.starlette_client import OAuth

logger = structlog.get_logger()
oauth = OAuth()

def setup_oauth(app: Any, settings: Any) -> None:
    """Register OAuth provider for token validation."""
    if settings.oauth_metadata_url:
        oauth.register(
            name="linkedin_mcp",
            server_metadata_url=settings.oauth_metadata_url,
            client_id=settings.oauth_client_id,
            client_secret=settings.oauth_client_secret,
        )

class OAuthMiddleware:
    """Validates Bearer tokens against an OAuth 2.1 authorization server."""

    def __init__(self, app: Any, oauth_config: Any, settings: Any = None) -> None:
        self.app = app
        self.oauth = oauth_config
        self.settings = settings

    async def _validate_token(self, token: str) -> bool:
        if not self.settings or not self.settings.oauth_server_url:
            return True  # Bypass introspection if OAuth URL is not configured

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{self.settings.oauth_server_url.rstrip('/')}/introspect",
                    data={"token": token},
                    auth=(self.settings.oauth_client_id or "", self.settings.oauth_client_secret or ""),
                )
                if resp.status_code == 200:
                    return bool(resp.json().get("active", False))
        except Exception as e:
            logger.warning("OAuth token introspection failed", error=str(e))
        return False

    async def _send_401(self, send: Any) -> None:
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({
            "type": "http.response.body",
            "body": b'{"error": "Unauthorized", "detail": "Invalid or expired OAuth token"}',
        })

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            auth = headers.get(b"authorization", b"").decode("utf-8")

            if auth.startswith("Bearer "):
                token = auth[7:]
                valid = await self._validate_token(token)
                if not valid:
                    await self._send_401(send)
                    return

        await self.app(scope, receive, send)
