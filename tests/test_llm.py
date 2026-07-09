from unittest.mock import AsyncMock, MagicMock

import pytest

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


@pytest.mark.asyncio
async def test_llm_provider_direct_anthropic() -> None:
    from unittest.mock import AsyncMock, patch

    provider = LLMProvider(api_key="fake-anthropic-key")

    mock_response = MagicMock()
    mock_response.json.return_value = {"content": [{"text": "Anthropic direct response"}]}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await provider.generate("Analyze this", system_prompt="Recruiter")
        assert result == "Anthropic direct response"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.anthropic.com/v1/messages"
        assert kwargs["headers"]["x-api-key"] == "fake-anthropic-key"


@pytest.mark.asyncio
async def test_llm_provider_direct_openai() -> None:
    from unittest.mock import AsyncMock, patch

    provider = LLMProvider(openai_api_key="fake-openai-key")

    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "OpenAI direct response"}}]}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await provider.generate("Analyze this", system_prompt="Recruiter")
        assert result == "OpenAI direct response"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.openai.com/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer fake-openai-key"
