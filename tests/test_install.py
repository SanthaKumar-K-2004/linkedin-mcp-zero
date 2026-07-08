import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from linkedin_mcp_zero.config.install import (
    config_path,
    install_client_config,
    verify_client_config,
)


def test_config_path_cwd(tmp_path) -> None:
    path = config_path("cursor", cwd=tmp_path)
    assert path == tmp_path / ".cursor" / "mcp.json"


def test_install_client_config_new_file(tmp_path) -> None:
    target = tmp_path / "mcp_config.json"

    res = install_client_config(
        client="claude-desktop",
        path=str(target),
        source="pypi",
    )

    assert res.changed is True
    assert res.backup is None
    assert target.exists()

    # Verify loaded contents
    with open(target) as f:
        data = json.load(f)
    assert "mcpServers" in data
    assert "linkedin-zero" in data["mcpServers"]
    assert "uvx" in data["mcpServers"]["linkedin-zero"]["command"]


def test_install_client_config_already_up_to_date(tmp_path) -> None:
    target = tmp_path / "mcp_config.json"

    # Install first time
    install_client_config(
        client="claude-desktop",
        path=str(target),
        source="pypi",
    )

    # Install second time
    res = install_client_config(
        client="claude-desktop",
        path=str(target),
        source="pypi",
    )
    assert res.changed is False
    assert res.backup is None


def test_install_client_config_backup_on_change(tmp_path) -> None:
    target = tmp_path / "mcp_config.json"
    target.write_text(json.dumps({"mcpServers": {"linkedin-zero": {"command": "old-command"}}}))

    res = install_client_config(
        client="claude-desktop",
        path=str(target),
        source="pypi",
    )
    assert res.changed is True
    assert res.backup is not None
    assert Path(res.backup).exists()


def test_verify_client_config_ok(tmp_path) -> None:
    target = tmp_path / "mcp_config.json"
    install_client_config(
        client="claude-desktop",
        path=str(target),
        source="pypi",
    )

    res = verify_client_config("claude-desktop", path=str(target))
    assert res.ok is True
    assert any(check["name"] == "mcpServers.linkedin-zero" and check["ok"] is True for check in res.checks)


def test_verify_client_config_missing(tmp_path) -> None:
    target = tmp_path / "missing_mcp_config.json"
    res = verify_client_config("claude-desktop", path=str(target))
    assert res.ok is False
    assert any(check["name"] == "mcpServers.linkedin-zero" and check["ok"] is False for check in res.checks)


@patch("linkedin_mcp_zero.config.install.subprocess.run")
@patch("linkedin_mcp_zero.config.install.shutil.which")
def test_install_claude_code(mock_which: MagicMock, mock_run: MagicMock) -> None:
    mock_which.return_value = "/bin/claude"
    mock_run.return_value = MagicMock(returncode=0)

    res = install_client_config("claude-code", source="pypi")
    assert res.client == "claude-code"
    assert res.changed is True
    mock_run.assert_called_once()
