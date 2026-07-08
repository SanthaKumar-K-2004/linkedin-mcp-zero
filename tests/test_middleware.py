import pytest
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from linkedin_mcp_zero.server.middleware import APIKeyAndRateLimitMiddleware

@pytest.mark.asyncio
async def test_middleware_options_request_passes() -> None:
    mock_app = AsyncMock()
    middleware = APIKeyAndRateLimitMiddleware(mock_app, api_key="secret-key")
    
    scope = {"type": "http", "method": "OPTIONS", "headers": []}
    receive = AsyncMock()
    send = AsyncMock()
    
    await middleware(scope, receive, send)
    mock_app.assert_called_once_with(scope, receive, send)

@pytest.mark.asyncio
async def test_middleware_unauthorized_missing_key() -> None:
    mock_app = AsyncMock()
    middleware = APIKeyAndRateLimitMiddleware(mock_app, api_key="secret-key")
    
    scope = {"type": "http", "method": "GET", "headers": [], "path": "/test"}
    receive = AsyncMock()
    send = AsyncMock()
    
    await middleware(scope, receive, send)
    
    # Assert app was NOT called
    mock_app.assert_not_called()
    
    # Assert unauthorized response sent
    send.assert_any_call({
        "type": "http.response.start",
        "status": 401,
        "headers": [(b"content-type", b"application/json")],
    })

@pytest.mark.asyncio
async def test_middleware_authorized_x_api_key() -> None:
    mock_app = AsyncMock()
    middleware = APIKeyAndRateLimitMiddleware(mock_app, api_key="secret-key")
    
    scope = {
        "type": "http",
        "method": "GET",
        "headers": [(b"x-api-key", b"secret-key")],
        "path": "/test",
    }
    receive = AsyncMock()
    send = AsyncMock()
    
    await middleware(scope, receive, send)
    mock_app.assert_called_once_with(scope, receive, send)

@pytest.mark.asyncio
async def test_middleware_authorized_bearer_token() -> None:
    mock_app = AsyncMock()
    middleware = APIKeyAndRateLimitMiddleware(mock_app, api_key="secret-key")
    
    scope = {
        "type": "http",
        "method": "GET",
        "headers": [(b"authorization", b"Bearer secret-key")],
        "path": "/test",
    }
    receive = AsyncMock()
    send = AsyncMock()
    
    await middleware(scope, receive, send)
    mock_app.assert_called_once_with(scope, receive, send)

@pytest.mark.asyncio
async def test_middleware_rate_limit_exceeded() -> None:
    mock_app = AsyncMock()
    middleware = APIKeyAndRateLimitMiddleware(mock_app, api_key="secret-key", rate_limit_per_minute=2)
    
    scope = {
        "type": "http",
        "method": "GET",
        "headers": [(b"x-api-key", b"secret-key")],
        "client": ("127.0.0.1", 12345),
        "path": "/test",
    }
    receive = AsyncMock()
    
    # 1st request
    send1 = AsyncMock()
    await middleware(scope, receive, send1)
    mock_app.assert_called_once()
    
    # 2nd request
    mock_app.reset_mock()
    send2 = AsyncMock()
    await middleware(scope, receive, send2)
    mock_app.assert_called_once()

    # 3rd request (limit exceeded)
    mock_app.reset_mock()
    send3 = AsyncMock()
    await middleware(scope, receive, send3)
    mock_app.assert_not_called()
    
    send3.assert_any_call({
        "type": "http.response.start",
        "status": 429,
        "headers": [(b"content-type", b"application/json")],
    })

@pytest.mark.asyncio
async def test_middleware_cleanup() -> None:
    mock_app = AsyncMock()
    middleware = APIKeyAndRateLimitMiddleware(mock_app, api_key="secret-key", rate_limit_per_minute=10)
    
    # Populate requests dictionary with more than 1000 items to trigger cleanup
    for i in range(1005):
        middleware.requests[f"10.0.0.{i}"] = [time.time()]
        
    scope = {
        "type": "http",
        "method": "GET",
        "headers": [(b"x-api-key", b"secret-key")],
        "client": ("127.0.0.1", 12345),
        "path": "/test",
    }
    receive = AsyncMock()
    send = AsyncMock()
    await middleware(scope, receive, send)
    
    # Since all the requests are active (time.time() within 60s), they shouldn't be pruned,
    # but the logic should run without exception and enforce limit
    assert len(middleware.requests) > 1000


from unittest.mock import patch
from linkedin_mcp_zero.utils.oauth import OAuthMiddleware

@pytest.mark.asyncio
async def test_oauth_middleware_bypass_when_no_server_url() -> None:
    mock_app = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.oauth_server_url = None
    
    middleware = OAuthMiddleware(mock_app, oauth_config=None, settings=mock_settings)
    scope = {
        "type": "http",
        "method": "GET",
        "headers": [(b"authorization", b"Bearer some-token")],
        "path": "/test",
    }
    receive = AsyncMock()
    send = MagicMock()
    
    await middleware(scope, receive, send)
    mock_app.assert_called_once_with(scope, receive, send)


@pytest.mark.asyncio
async def test_oauth_middleware_valid_token() -> None:
    mock_app = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.oauth_server_url = "http://mock-auth"
    mock_settings.oauth_client_id = "client"
    mock_settings.oauth_client_secret = "secret"
    
    middleware = OAuthMiddleware(mock_app, oauth_config=None, settings=mock_settings)
    scope = {
        "type": "http",
        "method": "GET",
        "headers": [(b"authorization", b"Bearer valid-token")],
        "path": "/test",
    }
    receive = AsyncMock()
    send = MagicMock()
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"active": True}
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        await middleware(scope, receive, send)
        
        mock_post.assert_called_once()
        mock_app.assert_called_once_with(scope, receive, send)


@pytest.mark.asyncio
async def test_oauth_middleware_invalid_token() -> None:
    mock_app = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.oauth_server_url = "http://mock-auth"
    mock_settings.oauth_client_id = "client"
    mock_settings.oauth_client_secret = "secret"
    
    middleware = OAuthMiddleware(mock_app, oauth_config=None, settings=mock_settings)
    scope = {
        "type": "http",
        "method": "GET",
        "headers": [(b"authorization", b"Bearer invalid-token")],
        "path": "/test",
    }
    receive = AsyncMock()
    send = AsyncMock()
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"active": False}
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        await middleware(scope, receive, send)
        
        mock_post.assert_called_once()
        mock_app.assert_not_called()
        send.assert_any_call({
            "type": "http.response.start",
            "status": 401,
            "headers": [(b"content-type", b"application/json")],
        })

