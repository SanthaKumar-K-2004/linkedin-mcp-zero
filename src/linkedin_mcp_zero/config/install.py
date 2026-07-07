from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

ClientName = Literal["claude-desktop", "claude-code", "cursor", "vscode"]
PackageSource = Literal["pypi", "github"]
PackageExtra = Literal["browser", "multi", "pdf"]


@dataclass(frozen=True)
class InstallResult:
    client: str
    path: str | None
    changed: bool
    backup: str | None
    server: str
    command: list[str] | None = None
    message: str = ""


@dataclass(frozen=True)
class VerifyResult:
    client: str
    ok: bool
    path: str | None
    checks: list[dict[str, object]]
    repair_hint: str


SERVER_NAME = "linkedin-zero"
GITHUB_URL = "git+https://github.com/SanthaKumar-K-2004/linkedin-mcp-zero"
FILE_CLIENTS: dict[str, dict[str, str]] = {
    "claude-desktop": {"key": "mcpServers"},
    "cursor": {"key": "mcpServers"},
    "vscode": {"key": "servers"},
}


def config_path(client: ClientName, cwd: Path | None = None) -> Path:
    system = platform.system()
    home = Path.home()
    if client == "cursor":
        base = cwd or Path.cwd()
        return base / ".cursor" / "mcp.json"
    if client == "vscode":
        if _is_wsl():
            return home / ".vscode-server" / "data" / "User" / "mcp.json"
        if system == "Darwin":
            return home / "Library" / "Application Support" / "Code" / "User" / "mcp.json"
        if system == "Windows":
            return home / "AppData" / "Roaming" / "Code" / "User" / "mcp.json"
        return home / ".config" / "Code" / "User" / "mcp.json"
    if client == "claude-code":
        return home / ".claude.json"
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
    extras: list[PackageExtra] | None = None,
    enable_browser: bool = False,
) -> InstallResult:
    enable_browser = enable_browser or "browser" in (extras or [])
    if client == "claude-code":
        return _install_claude_code(source, extras=extras, enable_browser=enable_browser)

    target = Path(path).expanduser() if path else config_path(client, cwd)
    config_key = _config_key(client)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = _load_json(target)
    servers = data.setdefault(config_key, {})
    if not isinstance(servers, dict):
        raise ValueError(f"Existing config has non-object `{config_key}`; refusing to overwrite.")

    server_config = server_config_for(source, extras=extras, enable_browser=enable_browser)
    old = servers.get(SERVER_NAME)
    if old == server_config:
        return InstallResult(
            client,
            str(target),
            False,
            None,
            SERVER_NAME,
            None,
            "Already current.",
        )

    backup = _backup(target) if target.exists() else None
    servers[SERVER_NAME] = server_config
    _atomic_write_json(target, data)
    return InstallResult(client, str(target), True, backup, SERVER_NAME, None, "Config updated.")


def verify_client_config(
    client: ClientName,
    *,
    path: str | None = None,
    cwd: Path | None = None,
) -> VerifyResult:
    if client == "claude-code":
        claude = shutil.which("claude")
        list_ok = False
        list_detail = "not checked"
        if claude:
            completed = subprocess.run(
                [claude, "mcp", "list"],
                check=False,
                capture_output=True,
                text=True,
            )
            output = (completed.stdout or completed.stderr or "").strip()
            list_ok = completed.returncode == 0 and SERVER_NAME in output
            list_detail = output or f"exit {completed.returncode}"
        checks = [
            {"name": "claude_cli_found", "ok": bool(claude), "detail": claude or "not found"},
            {
                "name": "claude_mcp_list_contains_linkedin_zero",
                "ok": list_ok,
                "detail": list_detail,
            },
        ]
        return VerifyResult(
            client=client,
            ok=all(bool(check["ok"]) for check in checks),
            path=None,
            checks=checks,
            repair_hint=("Install Claude Code CLI, then run `linkedin-mcp-zero --install-client claude-code`."),
        )

    target = Path(path).expanduser() if path else config_path(client, cwd)
    config_key = _config_key(client)
    checks: list[dict[str, object]] = []
    data: dict[str, Any] = {}
    try:
        data = _load_json(target)
        checks.append({"name": "valid_json", "ok": True, "detail": str(target)})
    except Exception as exc:
        checks.append({"name": "valid_json", "ok": False, "detail": str(exc)})

    servers = data.get(config_key) if data else None
    checks.append(
        {
            "name": f"{config_key}.{SERVER_NAME}",
            "ok": isinstance(servers, dict) and SERVER_NAME in servers,
            "detail": "server entry present" if isinstance(servers, dict) else "server map missing",
        }
    )
    entry = servers.get(SERVER_NAME) if isinstance(servers, dict) else {}
    command = str(entry.get("command", "")) if isinstance(entry, dict) else ""
    command_ok = bool(command and (Path(command).exists() or shutil.which(command)))
    checks.append({"name": "command_resolves", "ok": command_ok, "detail": command or "missing"})
    args = entry.get("args", []) if isinstance(entry, dict) else []
    args_ok = isinstance(args, list) and bool(args)
    checks.append({"name": "args_present", "ok": args_ok, "detail": args if args_ok else "missing"})
    if command_ok and args_ok:
        checks.append(_check_server_doctor(command, args))
    if client == "vscode":
        checks.append(
            {
                "name": "vscode_uses_servers_key",
                "ok": "servers" in data and "mcpServers" not in data,
                "detail": "VS Code requires top-level `servers`.",
            }
        )
    ok = all(bool(item["ok"]) for item in checks)
    return VerifyResult(
        client=client,
        ok=ok,
        path=str(target),
        checks=checks,
        repair_hint=f"Run `linkedin-mcp-zero --install-client {client}` to repair this config.",
    )


def _check_server_doctor(command: str, args: object) -> dict[str, object]:
    if not isinstance(args, list) or not args:
        return {"name": "server_doctor_runs", "ok": False, "detail": "missing args"}
    doctor_args = [str(part) for part in args] + ["--doctor", "--json"]
    try:
        completed = subprocess.run(
            [command, *doctor_args],
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except Exception as exc:
        return {"name": "server_doctor_runs", "ok": False, "detail": str(exc)}
    detail = (completed.stderr or completed.stdout or "").strip()
    return {
        "name": "server_doctor_runs",
        "ok": completed.returncode == 0,
        "detail": detail[:500] if detail else f"exit {completed.returncode}",
    }


def preview_config(
    source: PackageSource = "pypi",
    *,
    client: ClientName = "claude-desktop",
    extras: list[PackageExtra] | None = None,
    enable_browser: bool = False,
) -> dict[str, Any]:
    enable_browser = enable_browser or "browser" in (extras or [])
    if client == "claude-code":
        return {
            "command": claude_code_command(
                source,
                extras=extras,
                enable_browser=enable_browser,
            )
        }
    return {
        _config_key(client): {
            SERVER_NAME: server_config_for(
                source,
                extras=extras,
                enable_browser=enable_browser,
            )
        }
    }


def server_config_for(
    source: PackageSource = "pypi",
    *,
    extras: list[PackageExtra] | None = None,
    enable_browser: bool = False,
) -> dict[str, Any]:
    command = shutil.which("uvx") or "uvx"
    env = {
        "PATH": _merged_path(command),
        "HOME": str(Path.home()),
    }
    args = _uvx_args(source, extras=extras)
    if enable_browser:
        args.append("--enable-browser")
        env["LINKEDIN_MCP_ENABLE_BROWSER"] = "true"
    return {"command": command, "args": args, "env": env}


def claude_code_command(
    source: PackageSource = "pypi",
    *,
    extras: list[PackageExtra] | None = None,
    enable_browser: bool = False,
) -> list[str]:
    config = server_config_for(source, extras=extras, enable_browser=enable_browser)
    return [
        "claude",
        "mcp",
        "add-json",
        SERVER_NAME,
        json.dumps(config, ensure_ascii=True),
        "-s",
        "user",
    ]


def _install_claude_code(
    source: PackageSource,
    *,
    extras: list[PackageExtra] | None,
    enable_browser: bool,
) -> InstallResult:
    command = claude_code_command(source, extras=extras, enable_browser=enable_browser)
    if not shutil.which("claude"):
        return InstallResult(
            "claude-code",
            None,
            False,
            None,
            SERVER_NAME,
            command,
            "Claude Code CLI not found. Run the returned command after installing Claude Code.",
        )
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        return InstallResult(
            "claude-code",
            None,
            False,
            None,
            SERVER_NAME,
            command,
            (completed.stderr or completed.stdout or "Claude Code install failed.").strip(),
        )
    return InstallResult(
        "claude-code",
        None,
        True,
        None,
        SERVER_NAME,
        command,
        "Claude Code MCP added.",
    )


def _uvx_args(
    source: PackageSource = "pypi",
    *,
    extras: list[PackageExtra] | None = None,
) -> list[str]:
    if source == "github":
        return ["--from", _github_requirement(extras), "mcp-server-linkedin-zero"]
    if extras:
        return ["--from", _package_requirement(extras), "mcp-server-linkedin-zero"]
    return ["mcp-server-linkedin-zero"]


def _config_key(client: ClientName) -> str:
    if client not in FILE_CLIENTS:
        raise ValueError(f"{client} does not use a direct JSON config file.")
    return FILE_CLIENTS[client]["key"]


def _package_requirement(extras: list[PackageExtra] | None = None) -> str:
    clean = _clean_extras(extras)
    if not clean:
        return "mcp-server-linkedin-zero"
    return f"mcp-server-linkedin-zero[{','.join(clean)}]"


def _github_requirement(extras: list[PackageExtra] | None = None) -> str:
    clean = _clean_extras(extras)
    if not clean:
        return GITHUB_URL
    return f"mcp-server-linkedin-zero[{','.join(clean)}] @ {GITHUB_URL}"


def _clean_extras(extras: list[PackageExtra] | None = None) -> list[str]:
    allowed = {"browser", "multi", "pdf"}
    return sorted({extra for extra in extras or [] if extra in allowed})


def _merged_path(command: str) -> str:
    paths = [str(Path(command).parent)] if "/" in command else []
    paths.extend([str(Path.home() / ".local" / "bin"), "/usr/local/bin", "/usr/bin", "/bin"])
    existing = os.environ.get("PATH", "")
    paths.extend(part for part in existing.split(":") if part)
    return ":".join(dict.fromkeys(paths))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        corrupt = path.with_suffix(f"{path.suffix}.invalid.{datetime.now():%Y%m%d%H%M%S}.bak")
        shutil.copy2(path, corrupt)
        recovered = _load_latest_valid_backup(path)
        if recovered is None:
            raise ValueError(
                f"Config JSON is invalid at {path}: {exc}. A copy was saved to {corrupt}. Fix the JSON and rerun."
            ) from exc
        return recovered
    if not isinstance(data, dict):
        raise ValueError("Existing config root must be a JSON object.")
    return data


def _load_latest_valid_backup(path: Path) -> dict[str, Any] | None:
    backups = sorted(path.parent.glob(f"{path.name}*.bak"), key=lambda item: item.stat().st_mtime)
    for backup in reversed(backups):
        try:
            data = json.loads(backup.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            return data
    return None


def _backup(path: Path) -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup = path.with_suffix(f"{path.suffix}.{stamp}.bak")
    shutil.copy2(path, backup)
    return str(backup)


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _is_wsl() -> bool:
    try:
        release = Path("/proc/sys/kernel/osrelease").read_text(encoding="utf-8").lower()
    except OSError:
        return False
    return "microsoft" in release or "wsl" in release
