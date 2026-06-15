from pathlib import Path

import pytest

from linkedin_mcp_zero.config.autodetect import detect_runtime
from linkedin_mcp_zero.config.install import (
    claude_code_command,
    install_client_config,
    preview_config,
    verify_client_config,
)
from linkedin_mcp_zero.config.settings import Settings
from linkedin_mcp_zero.engines import multi_board
from linkedin_mcp_zero.engines.browser import BrowserEngine
from linkedin_mcp_zero.engines.resume import ResumeEngine
from linkedin_mcp_zero.engines.voyager import VoyagerEngine
from linkedin_mcp_zero.metrics.store import MetricsStore
from linkedin_mcp_zero.metrics.tracking import estimate_tokens
from linkedin_mcp_zero.server.app import create_app
from linkedin_mcp_zero.server.catalog import TOOLS, tool_help
from linkedin_mcp_zero.storage.db import Storage


def test_catalog_has_35_tools() -> None:
    assert len(TOOLS) == 35
    assert tool_help("sj")["name"] == "search_jobs"
    assert tool_help("gus")["name"] == "get_usage_stats"
    assert tool_help()["count"] == 35


def test_storage_alert_roundtrip(tmp_path: Path) -> None:
    storage = Storage(Settings(data_dir=str(tmp_path)))
    saved = storage.save_alert("Python Remote", "python", "remote")
    assert saved["id"] == 1
    assert storage.list_alerts()[0]["name"] == "Python Remote"


def test_resume_analysis_text(tmp_path: Path) -> None:
    resume_path = tmp_path / "resume.txt"
    resume_path.write_text(
        "Santhakumar K\nsan@example.com\nPython FastAPI SQL Docker Kubernetes",
        encoding="utf-8",
    )
    engine = ResumeEngine(Storage(Settings(data_dir=str(tmp_path / "data"))))
    result = engine.analyze_resume(str(resume_path))
    assert result["id"] == 1
    assert result["email"] == "san@example.com"
    assert "Python" in result["skills"]


def test_app_factory_creates_fastmcp(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=str(tmp_path)))
    assert app.name == "linkedin-mcp-zero"


def test_runtime_detects_resources(tmp_path: Path) -> None:
    runtime = detect_runtime(str(tmp_path))
    assert runtime["python_ok"] is True
    assert runtime["data_dir"] == str(tmp_path)
    assert runtime["mode"] in {"lean", "balanced", "full"}
    assert "optional" in runtime
    assert "notes" in runtime


def test_installer_preserves_existing_servers(tmp_path: Path) -> None:
    config = tmp_path / "claude.json"
    config.write_text(
        '{"mcpServers":{"other":{"command":"node","args":["server.js"]}}}\n',
        encoding="utf-8",
    )
    result = install_client_config("claude-desktop", path=str(config), source="github")
    text = config.read_text(encoding="utf-8")
    assert result.changed is True
    assert result.backup is not None
    assert '"other"' in text
    assert '"linkedin-zero"' in text
    assert "SanthaKumar-K-2004/linkedin-mcp-zero" in text


def test_installer_recovers_from_latest_valid_backup(tmp_path: Path) -> None:
    config = tmp_path / "claude.json"
    config.write_text('{"mcpServers":{"broken":', encoding="utf-8")
    backup = tmp_path / "claude.json.20260614212846.bak"
    backup.write_text(
        '{"mcpServers":{"other":{"command":"node","args":["server.js"]}}}\n',
        encoding="utf-8",
    )
    result = install_client_config("claude-desktop", path=str(config))
    data = config.read_text(encoding="utf-8")
    assert result.changed is True
    assert '"other"' in data
    assert '"linkedin-zero"' in data
    assert list(tmp_path.glob("claude.json.invalid.*.bak"))


def test_print_config_preview() -> None:
    config = preview_config()
    assert config["mcpServers"]["linkedin-zero"]["command"].endswith("uvx")
    github = preview_config("github")
    assert "--from" in github["mcpServers"]["linkedin-zero"]["args"]
    browser = preview_config(extras=["browser"])
    assert browser["mcpServers"]["linkedin-zero"]["args"] == [
        "--from",
        "mcp-server-linkedin-zero[browser]",
        "mcp-server-linkedin-zero",
        "--enable-browser",
    ]


def test_vscode_preview_uses_servers_key() -> None:
    config = preview_config(client="vscode")
    assert "servers" in config
    assert "mcpServers" not in config
    assert "linkedin-zero" in config["servers"]


def test_vscode_installer_preserves_existing_servers(tmp_path: Path) -> None:
    config = tmp_path / "vscode-mcp.json"
    config.write_text('{"servers":{"other":{"command":"node"}}}\n', encoding="utf-8")
    result = install_client_config("vscode", path=str(config))
    assert result.changed is True
    text = config.read_text(encoding="utf-8")
    assert '"servers"' in text
    assert '"mcpServers"' not in text
    assert '"other"' in text
    assert '"linkedin-zero"' in text


def test_verify_client_reports_missing_server(tmp_path: Path) -> None:
    config = tmp_path / "claude.json"
    config.write_text('{"mcpServers":{}}\n', encoding="utf-8")
    result = verify_client_config("claude-desktop", path=str(config))
    assert result.ok is False
    assert any(check["name"] == "mcpServers.linkedin-zero" for check in result.checks)


def test_claude_code_command_uses_add_json() -> None:
    command = claude_code_command()
    assert command[:4] == ["claude", "mcp", "add-json", "linkedin-zero"]
    assert "mcp-server-linkedin-zero" in command[4]


@pytest.mark.asyncio
async def test_browser_reports_unavailable_without_cdp(tmp_path: Path) -> None:
    engine = BrowserEngine(
        Settings(data_dir=str(tmp_path), cdp_url="http://127.0.0.1:9", timeout_seconds=1)
    )
    result = await engine.get_my_profile()
    assert result["available"] is False
    assert "start_chrome" in result


@pytest.mark.asyncio
async def test_browser_tools_are_hidden_by_default(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=str(tmp_path)))
    tools = await app.list_tools()
    names = {tool.name for tool in tools}
    assert "get_my_profile" not in names
    assert "get_profile_voyager" not in names
    assert "get_usage_stats" in names
    assert len(tools) == 23


@pytest.mark.asyncio
async def test_browser_tools_appear_when_enabled(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=str(tmp_path), enable_browser=True))
    tools = await app.list_tools()
    names = {tool.name for tool in tools}
    assert "get_my_profile" in names
    assert "check_session" in names


def test_metrics_store_tracks_no_payload(tmp_path: Path) -> None:
    store = MetricsStore(Settings(data_dir=str(tmp_path)))
    row_id = store.insert_call(
        tool_name="search_jobs",
        engine="public_no_login",
        called_at="2026-06-15T00:00:00+00:00",
        duration_ms=5,
        success=True,
        error_type=None,
        response_chars=16,
        response_bytes=16,
        tokens_estimated=estimate_tokens("a" * 16),
    )
    rows = store.recent_calls()
    assert row_id == 1
    assert rows[0]["tokens_estimated"] == 4
    assert "payload" not in rows[0]


@pytest.mark.asyncio
async def test_multi_board_falls_back_to_linkedin(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        async def search_jobs(self, kw: str, loc: str = "", limit: int = 5):
            return [{"id": "1", "t": kw, "loc": loc, "url": "https://example.com"}]

        async def close(self) -> None:
            return None

    monkeypatch.setattr(multi_board, "GuestAPIClient", FakeClient)
    result = await multi_board.search_jobs_multi("python", "remote", limit=1)
    assert result[0]["site"] == "linkedin"
    assert result[0]["multi_board_mode"] == "fallback_linkedin_only"


@pytest.mark.asyncio
async def test_usage_tool_is_not_self_recorded(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=str(tmp_path),
        exact_token_count=True,
        anthropic_api_key="test-key",
    )
    app = create_app(settings)
    result = await app.call_tool("get_usage_stats", {"limit": 5})
    assert result.structured_content["calls"] == []
    assert result.structured_content["exact_count_external_send"] is True
    assert MetricsStore(settings).recent_calls() == []


@pytest.mark.asyncio
async def test_voyager_is_gated_by_default(tmp_path: Path) -> None:
    engine = VoyagerEngine(Settings(data_dir=str(tmp_path)))
    result = await engine.get_profile("example")
    assert result["available"] is False
    assert result["enabled"] is False
