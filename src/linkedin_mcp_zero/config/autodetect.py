from __future__ import annotations

import os
import platform
import shutil
import sys
from dataclasses import asdict, dataclass
from importlib.util import find_spec
from pathlib import Path

from platformdirs import user_data_dir

from linkedin_mcp_zero.config.defaults import DATA_DIR_NAME


@dataclass(frozen=True)
class RuntimeStatus:
    os: str
    python: str
    python_ok: bool
    executable: str
    cpu_count: int | None
    ram_total_mb: int | None
    ram_available_mb: int | None
    disk_free_mb: int | None
    data_dir: str
    chrome: str | None
    cdp_url: str
    cdp_env_hint: bool
    docker: bool
    display: bool
    optional: dict[str, bool]
    mode: str
    notes: list[str]


def detect_chrome() -> str | None:
    candidates = [
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "brave-browser",
        "microsoft-edge",
    ]
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path
    return None


def detect_runtime(data_dir: str | None = None) -> dict[str, object]:
    ram_total, ram_available = _memory_mb()
    disk_free = _disk_free_mb(data_dir)
    optional = {
        "jobspy": _has_module("jobspy"),
        "pymupdf": _has_module("fitz"),
        "playwright": _has_module("playwright.async_api"),
        "patchright": _has_module("patchright.async_api"),
    }
    mode, notes = _recommend_mode(ram_available, disk_free, optional)
    status = RuntimeStatus(
        os=platform.system(),
        python=platform.python_version(),
        python_ok=sys.version_info >= (3, 10),
        executable=sys.executable,
        cpu_count=os.cpu_count(),
        ram_total_mb=ram_total,
        ram_available_mb=ram_available,
        disk_free_mb=disk_free,
        data_dir=str(_data_dir(data_dir)),
        chrome=detect_chrome(),
        cdp_url=os.environ.get("LINKEDIN_MCP_CDP_URL", "http://127.0.0.1:9222"),
        cdp_env_hint="LINKEDIN_MCP_CDP_URL" in os.environ,
        docker=os.path.exists("/.dockerenv"),
        display=bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")),
        optional=optional,
        mode=mode,
        notes=notes,
    )
    return asdict(status)


def _data_dir(data_dir: str | None = None) -> Path:
    return Path(data_dir or user_data_dir(DATA_DIR_NAME)).expanduser()


def _has_module(name: str) -> bool:
    try:
        return find_spec(name) is not None
    except ModuleNotFoundError:
        return False


def _disk_free_mb(data_dir: str | None = None) -> int | None:
    try:
        path = _data_dir(data_dir)
        path.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(path)
        return round(usage.free / 1024 / 1024)
    except OSError:
        return None


def _memory_mb() -> tuple[int | None, int | None]:
    if platform.system() == "Linux":
        try:
            values: dict[str, int] = {}
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                key, raw = line.split(":", 1)
                values[key] = int(raw.strip().split()[0])
            total = round(values["MemTotal"] / 1024)
            available = round(values.get("MemAvailable", values["MemFree"]) / 1024)
            return total, available
        except (OSError, KeyError, ValueError):
            return None, None
    if hasattr(os, "sysconf"):
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return round(pages * page_size / 1024 / 1024), None
        except (OSError, ValueError):
            return None, None
    return None, None


def _recommend_mode(
    ram_available_mb: int | None,
    disk_free_mb: int | None,
    optional: dict[str, bool],
) -> tuple[str, list[str]]:
    notes: list[str] = []
    mode = "full"
    if ram_available_mb is not None and ram_available_mb < 700:
        mode = "lean"
        notes.append("Low available RAM: keep Engine 2 browser closed until needed.")
    elif ram_available_mb is not None and ram_available_mb < 1500:
        mode = "balanced"
        notes.append("Moderate available RAM: Engine 1/local tools are preferred by default.")
    if disk_free_mb is not None and disk_free_mb < 512:
        mode = "lean"
        notes.append("Low disk space: avoid large exports and browser profiles.")
    if not optional["playwright"]:
        notes.append("Browser tools need `uv sync --extra browser`.")
    if not optional["jobspy"]:
        notes.append("Multi-board search needs `uv sync --extra multi`.")
    if not optional["pymupdf"]:
        notes.append("PDF resume parsing needs `uv sync --extra pdf`.")
    if not notes:
        notes.append("System looks ready for full zero-risk/local workflow.")
    return mode, notes
