from __future__ import annotations

import inspect
import os
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

import structlog

logger = structlog.get_logger()

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False

_tracer = None


def get_tracer() -> Any:
    global _tracer
    if OPENTELEMETRY_AVAILABLE and _tracer is None:
        try:
            from opentelemetry import trace

            _tracer = trace.get_tracer("linkedin-mcp-zero")
        except Exception:
            pass
    return _tracer


def init_telemetry() -> None:
    """Initialize OpenTelemetry tracer with console exporter."""
    if not os.environ.get("LINKEDIN_MCP_ENABLE_TELEMETRY"):
        return

    global _tracer
    if OPENTELEMETRY_AVAILABLE:
        try:
            provider = TracerProvider()
            processor = BatchSpanProcessor(ConsoleSpanExporter())
            provider.add_span_processor(processor)
            trace.set_tracer_provider(provider)
            _tracer = trace.get_tracer("linkedin-mcp-zero")
            logger.info("OpenTelemetry tracing initialized successfully")
        except Exception as e:
            logger.warning("Failed to initialize OpenTelemetry tracing", error=str(e))


F = TypeVar("F", bound=Callable[..., Any])


def trace_span(name: str) -> Callable[[F], F]:
    """Decorator to trace a synchronous or asynchronous function."""

    def decorator(fn: F) -> F:
        if not OPENTELEMETRY_AVAILABLE or _tracer is None:
            return fn

        if inspect.iscoroutinefunction(fn):

            @wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with _tracer.start_as_current_span(name):
                    return await fn(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]
        else:

            @wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                with _tracer.start_as_current_span(name):
                    return fn(*args, **kwargs)

            return sync_wrapper  # type: ignore[return-value]

    return decorator
