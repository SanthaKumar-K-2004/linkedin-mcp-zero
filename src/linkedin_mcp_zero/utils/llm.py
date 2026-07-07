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

        # Heuristic analysis fallback for offline/non-sampling environments
        name = "Candidate"
        skills = []

        for line in prompt.split("\n"):
            if line.startswith("Name:"):
                name = line.replace("Name:", "").strip()
            elif line.startswith("Skills:"):
                skills = [s.strip() for s in line.replace("Skills:", "").split(",") if s.strip()]

        if not skills:
            return (
                f"[Local Fallback Analysis]\n"
                f"Candidate: {name}\n"
                f"No explicit skills parsed from prompt. Details: {prompt[:100]}..."
            )

        all_modern_skills = {"docker", "kubernetes", "aws", "gcp", "ci/cd", "rust", "golang", "typescript", "react"}
        missing_skills = [s.title() for s in all_modern_skills if s not in {sk.lower() for sk in skills}][:3]
        strengths = [s.title() for s in skills[:3]]

        return f"""[Local Heuristic Analysis Fallback]
Candidate Profile Analysis: {name}

1. Executive Summary:
The candidate {name} has a strong foundation with skills in {", ".join(skills[:5])}. This profile is well-suited for roles matching these technologies, with opportunities to expand into modern cloud-native systems.

2. Top 3 Strengths:
- Proficient in {strengths[0] if len(strengths) > 0 else "Core Technologies"}
- Experience with {strengths[1] if len(strengths) > 1 else "Development Lifecycle"}
- Foundational skills in {strengths[2] if len(strengths) > 2 else "Software Engineering"}

3. Key Areas of Improvement & Missing Skills:
- Missing coverage for modern tools: {", ".join(missing_skills) if missing_skills else "No major skill gaps identified."}
- Could benefit from adding cloud-native deployment experience.

4. Tailored Recommendations:
- Highlight concrete project accomplishments and metrics on the resume.
- List specific backend framework versions and database scaling experiences.
- Detail containerization and CI/CD pipeline automation setup.
"""
