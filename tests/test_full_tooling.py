from pathlib import Path

import pytest

from linkedin_mcp_zero.config.autodetect import detect_runtime
from linkedin_mcp_zero.config.install import install_client_config, preview_config
from linkedin_mcp_zero.config.settings import Settings
from linkedin_mcp_zero.engines.browser import BrowserEngine
from linkedin_mcp_zero.engines.resume import ResumeEngine
from linkedin_mcp_zero.engines.voyager import VoyagerEngine
from linkedin_mcp_zero.server.app import create_app
from linkedin_mcp_zero.server.catalog import TOOLS, tool_help
from linkedin_mcp_zero.storage.db import Storage


def test_catalog_has_32_tools() -> None:
    assert len(TOOLS) == 32
    assert tool_help("sj")["name"] == "search_jobs"
    assert tool_help()["count"] == 32


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


@pytest.mark.asyncio
async def test_browser_reports_unavailable_without_cdp(tmp_path: Path) -> None:
    engine = BrowserEngine(
        Settings(data_dir=str(tmp_path), cdp_url="http://127.0.0.1:9", timeout_seconds=1)
    )
    result = await engine.get_my_profile()
    assert result["available"] is False
    assert "start_chrome" in result


@pytest.mark.asyncio
async def test_voyager_is_gated_by_default(tmp_path: Path) -> None:
    engine = VoyagerEngine(Settings(data_dir=str(tmp_path)))
    result = await engine.get_profile("example")
    assert result["available"] is False
    assert result["enabled"] is False
