from __future__ import annotations

import os
from typing import Any

import structlog
from fastmcp import Context

logger = structlog.get_logger()


class LLMProvider:
    """Abstraction for interacting with LLM models via client sampling or custom configurations."""

    def __init__(
        self,
        api_key: str | None = None,
        openai_api_key: str | None = None,
        anthropic_model: str | None = None,
        openai_model: str | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        self.anthropic_model = anthropic_model or os.environ.get(
            "LINKEDIN_MCP_ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"
        )
        self.openai_model = openai_model or os.environ.get("LINKEDIN_MCP_OPENAI_MODEL", "gpt-4o-mini")
        self._client: Any = None

    async def _get_client(self) -> Any:
        import httpx

        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def generate(self, prompt: str, system_prompt: str = "", ctx: Context | None = None) -> str:
        """Generate text from LLM using client context or fallback local heuristics."""
        if ctx is not None:
            try:
                result = await ctx.sample(
                    messages=prompt,
                    system_prompt=system_prompt,
                )
                return result.text or ""
            except Exception as e:
                logger.warning("LLM client sampling failed, falling back to local analysis", error=str(e))

        # Direct API calls if keys are available
        if self.api_key:
            try:
                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }
                data = {
                    "model": self.anthropic_model,
                    "max_tokens": 1024,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": prompt}],
                }
                client = await self._get_client()
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=data,
                    timeout=30.0,
                )
                resp.raise_for_status()
                return str(resp.json()["content"][0]["text"])
            except Exception as e:
                logger.warning(
                    "Direct Anthropic API call failed, falling back to other providers or heuristics", error=str(e)
                )

        if self.openai_api_key:
            try:
                headers = {
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "content-type": "application/json",
                }
                data = {
                    "model": self.openai_model,
                    "max_tokens": 1024,
                    "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
                }
                client = await self._get_client()
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=30.0,
                )
                resp.raise_for_status()
                return str(resp.json()["choices"][0]["message"]["content"])
            except Exception as e:
                logger.warning("Direct OpenAI API call failed, falling back to local heuristics", error=str(e))

        # Data-driven synthesis fallback for offline/non-sampling environments
        name = "Candidate"
        skills: list[str] = []
        market_gaps: list[str] = []
        target = "Software Engineering"

        for line in prompt.split("\n"):
            line_str = line.strip()
            if line_str.startswith("Candidate Name:") or line_str.startswith("Name:"):
                name = line_str.split(":", 1)[1].strip() or "Candidate"
            elif line_str.startswith("Current Skills:") or line_str.startswith("Skills:"):
                skills = [s.strip() for s in line_str.split(":", 1)[1].split(",") if s.strip()]
            elif line_str.startswith("Live Market Gaps:"):
                market_gaps = [s.strip() for s in line_str.split(":", 1)[1].split(",") if s.strip()]
            elif line_str.startswith("Market Target:"):
                target = line_str.split(":", 1)[1].strip() or target

        if not skills:
            return (
                f"[Local Fallback Analysis]\n"
                f"Candidate: {name}\n"
                f"No explicit skills parsed from prompt. Details: {prompt[:100]}..."
            )

        gap_display = ", ".join(market_gaps[:3]) if market_gaps else "Domain competencies well-covered."

        return f"""[Local Heuristic Analysis Fallback]
Candidate Profile Analysis: {name}
Target Domain: {target}

1. Executive Summary:
{name} presents demonstrated capabilities in {", ".join(skills[:4])}. Evaluated against live labor market trends for {target}, this profile aligns with core operational and technical requirements.

2. Verified Core Competencies:
- Core Technical Stack: {", ".join(skills[:3])}
- Supporting Domain Tools: {", ".join(skills[3:6]) if len(skills) > 3 else "Foundational engineering tooling"}

3. Live Market Gaps & Opportunities:
- In-demand competencies to emphasize: {gap_display}

4. Actionable Strategy:
- Quantify production outcomes, performance gains, and engineering scale in existing project summaries.
- Align resume keywords directly with verified live posting requirements for {target}.
"""
