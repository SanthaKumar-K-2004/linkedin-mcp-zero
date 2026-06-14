from __future__ import annotations


class LinkedInMCPError(Exception):
    """Base exception for user-facing MCP errors."""


class UpstreamError(LinkedInMCPError):
    """Raised when a public upstream endpoint fails."""


class ParseError(LinkedInMCPError):
    """Raised when public HTML cannot be parsed."""


class RateLimitError(LinkedInMCPError):
    """Raised when local pacing rejects a request."""
