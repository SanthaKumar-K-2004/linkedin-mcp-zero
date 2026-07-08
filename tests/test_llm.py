import pytest
from unittest.mock import AsyncMock, MagicMock
from linkedin_mcp_zero.utils.llm import LLMProvider

@pytest.mark.asyncio
async def test_llm_provider_fallback() -> None:
    provider = LLMProvider()
    prompt = "Name: John Doe\nSkills: Python, Go, Docker"
    result = await provider.generate(prompt)
    assert "[Local Heuristic Analysis Fallback]" in result
    assert "John Doe" in result
    assert "Python" in result

@pytest.mark.asyncio
async def test_llm_provider_no_skills_fallback() -> None:
    provider = LLMProvider()
    prompt = "Just some text without structured skills"
    result = await provider.generate(prompt)
    assert "[Local Fallback Analysis]" in result

@pytest.mark.asyncio
async def test_llm_provider_sampling() -> None:
    provider = LLMProvider()
    mock_ctx = MagicMock()
    mock_sample_result = MagicMock()
    mock_sample_result.text = "Generated cover letter"
    mock_ctx.sample = AsyncMock(return_value=mock_sample_result)

    result = await provider.generate("Write a letter", ctx=mock_ctx)
    assert result == "Generated cover letter"
    mock_ctx.sample.assert_called_once()
