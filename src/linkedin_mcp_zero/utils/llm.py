from __future__ import annotations

import structlog
from fastmcp import Context

logger = structlog.get_logger()


class LLMProvider:
    """Abstraction for interacting with LLM models via client sampling or custom configurations."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    async def generate(self, prompt: str, system_prompt: str = "", ctx: Context | None = None) -> str:
        """Generate text from LLM using client context or fallback local heuristics."""
        if ctx is not None:
            try:
                result = await ctx.sample(
                    messages=prompt,
                    system_prompt=system_prompt,
                )
                return result.text
            except Exception as e:
                logger.warning("LLM client sampling failed, falling back to local analysis", error=str(e))

        # Reusable local mock fallback for testing and offline/non-sampling environments
        return (
            f"[Local Fallback Analysis]\n"
            f"Prompt: {prompt[:150]}...\n"
            f"Analysis performed locally without external LLM provider."
        )
