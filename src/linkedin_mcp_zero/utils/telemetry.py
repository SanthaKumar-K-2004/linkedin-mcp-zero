from __future__ import annotations

from collections.abc import Callable
from functools import wraps
import inspect
from typing import Any

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


def init_telemetry() -> None:
    """Initialize OpenTelemetry tracer with console exporter."""
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


def trace_span(name: str) -> Callable[..., Any]:
    """Decorator to trace a synchronous or asynchronous function."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if not OPENTELEMETRY_AVAILABLE or _tracer is None:
            return fn

        if inspect.iscoroutinefunction(fn):

            @wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with _tracer.start_as_current_span(name):
                    return await fn(*args, **kwargs)

            return async_wrapper
        else:

            @wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                with _tracer.start_as_current_span(name):
                    return fn(*args, **kwargs)

            return sync_wrapper

    return decorator
