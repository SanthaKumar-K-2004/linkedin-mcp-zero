from __future__ import annotations

import asyncio
import json
import math
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import datetime, timezone
from functools import wraps
from typing import Any, TypeVar, cast

import httpx

from linkedin_mcp_zero.config.settings import Settings
from linkedin_mcp_zero.metrics.store import MetricsStore

F = TypeVar("F", bound=Callable[..., Any])


def estimate_tokens(content: str) -> int:
    return math.ceil(len(content) / 4)


def serialize_result(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"), default=str)
    except TypeError:
        return str(value)


def track_async_tool(
    func: Callable[..., Awaitable[Any]],
    *,
    store: MetricsStore,
    settings: Settings,
    engine: str,
    tool_name: str | None = None,
) -> Callable[..., Awaitable[Any]]:
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        called_at = datetime.now(timezone.utc).isoformat()
        result: Any = None
        success = False
        error_type: str | None = None
        try:
            result = await func(*args, **kwargs)
            success = True
            return result
        except Exception as exc:
            error_type = type(exc).__name__
            raise
        finally:
            _record_call(
                store,
                settings,
                tool_name or func.__name__,
                engine,
                called_at,
                int((time.monotonic() - start) * 1000),
                success,
                error_type,
                result,
            )

    return wrapper


def track_sync_tool(
    func: F,
    *,
    store: MetricsStore,
    settings: Settings,
    engine: str,
    tool_name: str | None = None,
) -> F:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        called_at = datetime.now(timezone.utc).isoformat()
        result: Any = None
        success = False
        error_type: str | None = None
        try:
            result = func(*args, **kwargs)
            success = True
            return result
        except Exception as exc:
            error_type = type(exc).__name__
            raise
        finally:
            _record_call(
                store,
                settings,
                tool_name or func.__name__,
                engine,
                called_at,
                int((time.monotonic() - start) * 1000),
                success,
                error_type,
                result,
            )

    return cast(F, wrapper)


def _record_call(
    store: MetricsStore,
    settings: Settings,
    tool_name: str,
    engine: str,
    called_at: str,
    duration_ms: int,
    success: bool,
    error_type: str | None,
    result: Any,
) -> None:
    content = serialize_result(result) if result is not None else ""
    row_id = store.insert_call(
        tool_name=tool_name,
        engine=engine,
        called_at=called_at,
        duration_ms=duration_ms,
        success=success,
        error_type=error_type,
        response_chars=len(content),
        response_bytes=len(content.encode("utf-8")),
        tokens_estimated=estimate_tokens(content),
    )
    if settings.exact_token_count and settings.anthropic_api_key and content:
        with suppress(RuntimeError):
            asyncio.get_running_loop().create_task(_count_exact(settings, store, row_id, content))


async def _count_exact(
    settings: Settings,
    store: MetricsStore,
    row_id: int,
    content: str,
) -> None:
    headers = {
        "x-api-key": settings.anthropic_api_key or "",
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": settings.token_count_model,
        "messages": [{"role": "user", "content": content}],
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages/count_tokens",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        tokens = int(data.get("input_tokens", 0))
    except Exception:
        return
    if tokens > 0:
        store.update_exact_tokens(row_id, tokens)
