from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


class _StderrPrintLoggerFactory:
    """structlog logger factory resolved against the *current* sys.stderr.

    MCP stdio transport owns stdout exclusively for JSON-RPC frames, so every
    log line must go to stderr. Resolving sys.stderr at emit time (instead of
    binding it once at configure time) keeps logging correct even when the
    embedding process or a test runner swaps the stream object, and avoids
    caching loggers against streams that later get closed.
    """

    def __call__(self, *args: Any, **kwargs: Any) -> structlog.PrintLogger:
        return structlog.PrintLogger(sys.stderr)


def configure_logging(level: str = "INFO") -> None:
    """Configure stdlib + structlog logging; all output goes to stderr only."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=numeric_level, format="%(message)s", stream=sys.stderr, force=True)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=_StderrPrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        cache_logger_on_first_use=False,
    )
