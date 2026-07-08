from __future__ import annotations

import argparse
import json
import secrets

from rich.console import Console
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from linkedin_mcp_zero.config.autodetect import detect_runtime
from linkedin_mcp_zero.config.install import (
    PackageExtra,
    install_client_config,
    preview_config,
    verify_client_config,
)
from linkedin_mcp_zero.config.settings import Settings
from linkedin_mcp_zero.server.app import create_app
from linkedin_mcp_zero.server.middleware import APIKeyAndRateLimitMiddleware
from linkedin_mcp_zero.utils.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="linkedin-mcp-zero")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--log-level", default=None)
    parser.add_argument("--json", action="store_true", dest="json_output", help="Print JSON output")
    parser.add_argument("--enable-browser", action="store_true", help="Expose opt-in browser tools")
    parser.add_argument("--enable-voyager", action="store_true")
    parser.add_argument("--doctor", action="store_true", help="Print auto-detected runtime status")
    parser.add_argument(
        "--install-client",
        choices=["claude-desktop", "claude-code", "cursor", "vscode"],
        default=None,
        help="Safely merge this MCP into a client config",
    )
    parser.add_argument(
        "--verify-client",
        choices=["claude-desktop", "claude-code", "cursor", "vscode"],
        default=None,
        help="Verify an installed MCP client config",
    )
    parser.add_argument(
        "--client",
        choices=["claude-desktop", "claude-code", "cursor", "vscode"],
        default="claude-desktop",
        help="Client shape for --print-config",
    )
    parser.add_argument(
        "--package-source",
        choices=["pypi", "github"],
        default="pypi",
        help="Use PyPI package command or GitHub repo command in installed MCP config",
    )
    parser.add_argument(
        "--with-extra",
        action="append",
        choices=["browser", "multi", "pdf"],
        default=[],
        help="Include an optional package extra in installed/printed MCP config",
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
    if args.enable_browser:
        settings.enable_browser = True

    configure_logging(settings.log_level)
    if args.doctor:
        runtime = detect_runtime(settings.data_dir)
        if args.json_output:
            Console().print_json(json.dumps(runtime, default=str))
        else:
            _print_doctor(runtime)
        return
    extras: list[PackageExtra] = args.with_extra
    if args.print_config:
        Console().print_json(
            json.dumps(
                preview_config(
                    args.package_source,
                    client=args.client,
                    extras=extras,
                    enable_browser=settings.enable_browser,
                )
            )
        )
        return
    if args.install_client:
        install_res = install_client_config(
            args.install_client,
            path=args.config_path,
            source=args.package_source,
            extras=extras,
            enable_browser=settings.enable_browser,
        )
        Console().print_json(json.dumps(install_res.__dict__, default=str))
        return
    if args.verify_client:
        verify_res = verify_client_config(args.verify_client, path=args.config_path)
        Console().print_json(json.dumps(verify_res.__dict__, default=str))
        return

    DISCLAIMER = (
        "\n[bold yellow]SAFE USE NOTICE & DISCLAIMER:[/bold yellow]\n"
        "This tool is for educational & research purposes only. Automated scraping of LinkedIn\n"
        "may violate their Terms of Service and could lead to account restrictions or IP blocks.\n"
        "Always use public guest endpoints or browser/voyager/sampling modes responsibly.\n"
    )
    Console(stderr=True).print(DISCLAIMER)

    app = create_app(settings)
    if settings.transport == "streamable-http":
        from starlette.requests import Request
        from starlette.responses import JSONResponse

        try:
            from linkedin_mcp_zero.utils.oauth import OAuthMiddleware, oauth
        except ImportError:
            console = Console()
            console.print(
                "[bold red]ERROR:[/bold red] OAuth dependencies are missing. "
                "Install them using `pip install mcp-server-linkedin-zero[oauth]`"
            )
            raise SystemExit(1) from None

        @app.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
        async def oauth_protected_resource(request: Request) -> JSONResponse:
            return JSONResponse(
                {
                    "resource": f"http://{settings.host}:{settings.port}",
                    "authorization_servers": [settings.oauth_server_url] if settings.oauth_server_url else [],
                    "scopes_supported": ["jobs:read", "profile:read", "alerts:manage"],
                    "bearer_methods_supported": ["header"],
                }
            )

        api_key = settings.api_key
        if not api_key:
            api_key = secrets.token_hex(16)
            console = Console()
            console.print(
                "[bold yellow]WARNING:[/bold yellow] No API key configured for HTTP transport. "
                f"Generated secure API key: [bold green]{api_key}[/bold green]"
            )

        cors_origins = settings.cors_allowed_origins
        allow_creds = True
        if "*" in cors_origins:
            allow_creds = False

        # Note on Starlette middleware execution order:
        # In Starlette, the middleware stack is evaluated in reverse order (bottom-up).
        # Therefore, incoming requests execute in the following sequence:
        # 1. APIKeyAndRateLimitMiddleware (validates API key or Bearer token API key)
        # 2. OAuthMiddleware (validates Bearer token against OAuth 2.1 auth server if enabled)
        # 3. CORSMiddleware (evaluates CORS headers)
        middleware_list = [
            Middleware(
                CORSMiddleware,
                allow_origins=cors_origins,
                allow_credentials=allow_creds,
                allow_methods=["*"],
                allow_headers=["*"],
            ),
            Middleware(
                OAuthMiddleware,
                oauth_config=oauth,
                settings=settings,
            ),
            Middleware(
                APIKeyAndRateLimitMiddleware,
                api_key=api_key,
                rate_limit_per_minute=settings.rate_limit_per_minute,
            ),
        ]

        app.run(
            transport="streamable-http",
            host=settings.host,
            port=settings.port,
            show_banner=False,
            middleware=middleware_list,
        )
    else:
        app.run(transport="stdio", show_banner=False)


def _print_doctor(runtime: dict[str, object]) -> None:
    console = Console()
    optional = runtime.get("optional", {})
    notes = runtime.get("notes", [])
    console.print("[bold]LinkedIn MCP Zero Doctor[/bold]")
    console.print(f"OS: {runtime.get('os')} | Python: {runtime.get('python')}")
    console.print(f"Executable: {runtime.get('executable')}")
    console.print(
        f"CPU: {runtime.get('cpu_count')} | RAM available: {runtime.get('ram_available_mb')} MB | "
        f"Disk free: {runtime.get('disk_free_mb')} MB"
    )
    console.print(f"Data dir: {runtime.get('data_dir')}")
    console.print(f"Chrome: {runtime.get('chrome') or 'not found'}")
    console.print(f"CDP URL: {runtime.get('cdp_url')}")
    console.print(f"Recommended mode: {runtime.get('mode')}")
    if isinstance(optional, dict):
        console.print("Optional packages:")
        for name, available in optional.items():
            console.print(f"  {'OK' if available else 'NO'} {name}")
    if isinstance(notes, list):
        console.print("Notes:")
        for note in notes:
            console.print(f"  - {note}")
    console.print(
        'Browser extra fix: uvx --from "mcp-server-linkedin-zero[browser]" mcp-server-linkedin-zero --doctor',
        markup=False,
    )
