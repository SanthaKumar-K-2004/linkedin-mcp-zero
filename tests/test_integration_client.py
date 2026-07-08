import pytest
from fastmcp.client import Client

from linkedin_mcp_zero.server.app import create_app


@pytest.mark.asyncio
async def test_client_integration_roundtrip() -> None:
    """Test full MCP client-server roundtrip using the real fastmcp Client."""
    app = create_app()
    async with Client(app) as client:
        # 1. Test listing tools
        tools = await client.list_tools()
        assert len(tools) >= 30

        # 2. Test tool execution (get_help)
        result = await client.call_tool("get_help")
        assert not result.is_error
        assert "count" in result.data
        assert "tools" in result.data

        # 3. Test tool execution (get_engine_status)
        status_res = await client.call_tool("get_engine_status")
        assert not status_res.is_error
        assert "tool_count" in status_res.data
        assert "engines" in status_res.data
