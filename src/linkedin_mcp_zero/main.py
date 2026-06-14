from __future__ import annotations

import argparse
import json

from rich.console import Console

from linkedin_mcp_zero.config.autodetect import detect_runtime
from linkedin_mcp_zero.config.install import install_client_config, preview_config
from linkedin_mcp_zero.config.settings import Settings
from linkedin_mcp_zero.server.app import create_app
from linkedin_mcp_zero.utils.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="linkedin-mcp-zero")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--log-level", default=None)
    parser.add_argument("--enable-voyager", action="store_true")
    parser.add_argument("--doctor", action="store_true", help="Print auto-detected runtime status")
    parser.add_argument(
        "--install-client",
        choices=["claude-desktop", "cursor"],
        default=None,
        help="Safely merge this MCP into a client config",
    )
    parser.add_argument(
        "--package-source",
        choices=["pypi", "github"],
        default="pypi",
        help="Use PyPI package command or GitHub repo command in installed MCP config",
    )
    parser.add_argument(
        "--config-path",
        default=None,
        help="Override config path for --install-client",
    )
    parser.add_argument("--print-config", action="store_true", help="Print MCP JSON config snippet")
    return parser


def cli() -> None:
    args = build_parser().parse_args()
    settings = Settings()
    if args.transport:
        settings.transport = args.transport
    if args.host:
        settings.host = args.host
    if args.port:
        settings.port = args.port
    if args.log_level:
        settings.log_level = args.log_level
    if args.enable_voyager:
        settings.enable_voyager = True

    configure_logging(settings.log_level)
    if args.doctor:
        Console().print_json(json.dumps(detect_runtime(settings.data_dir), default=str))
        return
    if args.print_config:
        Console().print_json(json.dumps(preview_config(args.package_source)))
        return
    if args.install_client:
        result = install_client_config(
            args.install_client,
            path=args.config_path,
            source=args.package_source,
        )
        Console().print_json(json.dumps(result.__dict__, default=str))
        return

    app = create_app(settings)
    if settings.transport == "streamable-http":
        app.run(transport="streamable-http", host=settings.host, port=settings.port)
    else:
        app.run(transport="stdio")
