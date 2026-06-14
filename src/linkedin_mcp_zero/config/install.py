from __future__ import annotations

import json
import platform
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

ClientName = Literal["claude-desktop", "cursor"]
PackageSource = Literal["pypi", "github"]


@dataclass(frozen=True)
class InstallResult:
    client: str
    path: str
    changed: bool
    backup: str | None
    server: str


SERVER_NAME = "linkedin-zero"
PYPI_SERVER_CONFIG = {"command": "uvx", "args": ["mcp-server-linkedin-zero"]}
GITHUB_SERVER_CONFIG = {
    "command": "uvx",
    "args": [
        "--from",
        "git+https://github.com/SanthaKumar-K-2004/linkedin-mcp-zero",
        "mcp-server-linkedin-zero",
    ],
}


def config_path(client: ClientName, cwd: Path | None = None) -> Path:
    system = platform.system()
    home = Path.home()
    if client == "cursor":
        base = cwd or Path.cwd()
        return base / ".cursor" / "mcp.json"
    if system == "Darwin":
        return home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if system == "Windows":
        return home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    return home / ".config" / "Claude" / "claude_desktop_config.json"


def install_client_config(
    client: ClientName,
    *,
    path: str | None = None,
    cwd: Path | None = None,
    source: PackageSource = "pypi",
) -> InstallResult:
    target = Path(path).expanduser() if path else config_path(client, cwd)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = _load_json(target)
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError("Existing config has non-object `mcpServers`; refusing to overwrite.")

    server_config = server_config_for(source)
    old = servers.get(SERVER_NAME)
    if old == server_config:
        return InstallResult(client, str(target), False, None, SERVER_NAME)

    backup = _backup(target) if target.exists() else None
    servers[SERVER_NAME] = server_config
    _atomic_write_json(target, data)
    return InstallResult(client, str(target), True, backup, SERVER_NAME)


def preview_config(source: PackageSource = "pypi") -> dict[str, Any]:
    return {"mcpServers": {SERVER_NAME: server_config_for(source)}}


def server_config_for(source: PackageSource = "pypi") -> dict[str, Any]:
    if source == "github":
        return GITHUB_SERVER_CONFIG
    return PYPI_SERVER_CONFIG


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Existing config root must be a JSON object.")
    return data


def _backup(path: Path) -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup = path.with_suffix(f"{path.suffix}.{stamp}.bak")
    shutil.copy2(path, backup)
    return str(backup)


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    tmp.replace(path)
