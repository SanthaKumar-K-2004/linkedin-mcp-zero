<div align="center">

```text
██╗     ██╗███╗   ██╗██╗  ██╗███████╗██████╗ ██╗███╗   ██╗
██║     ██║████╗  ██║██║ ██╔╝██╔════╝██╔══██╗██║████╗  ██║
██║     ██║██╔██╗ ██║█████╔╝ █████╗  ██║  ██║██║██╔██╗ ██║
██║     ██║██║╚██╗██║██╔═██╗ ██╔══╝  ██║  ██║██║██║╚██╗██║
███████╗██║██║ ╚████║██║  ██╗███████╗██████╔╝██║██║ ╚████║
╚══════╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝╚═════╝ ╚═╝╚═╝  ╚═══╝
             MCP ZERO - public-first LinkedIn intelligence
```

# LinkedIn MCP Zero

**32 MCP tools for jobs, resumes, matching, alerts, exports, and optional read-only browser intelligence.**

No Docker required · Public-first · Low-RAM friendly · FastMCP · PyPI published

[![PyPI](https://img.shields.io/pypi/v/mcp-server-linkedin-zero?color=0A66C2)](https://pypi.org/project/mcp-server-linkedin-zero/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-stdio%20%7C%20http-purple)](https://modelcontextprotocol.io/)

</div>

## The Promise

LinkedIn MCP Zero gives AI agents useful LinkedIn intelligence while staying
honest about risk:

| Principle | What it means |
|---|---|
| Public-first | Job search/details use public LinkedIn guest endpoints. No account required. |
| Read-only | No automated posting, applying, connecting, or messaging. |
| Local by default | Resume parsing, alerts, matching, exports, and state live on your machine. |
| Lazy browser | Chrome/CDP tools load only when called, then auto-unload after idle time. |
| Low-spec friendly | The server detects RAM/disk and recommends `full`, `balanced`, or `lean`. |
| Easy install | Claude Code, Claude Desktop, Cursor, and custom MCP clients work with one command. |

## Install In 10 Seconds

Check your system:

```bash
uvx mcp-server-linkedin-zero --doctor
```

Run as an MCP server:

```bash
uvx mcp-server-linkedin-zero
```

Use the latest GitHub source instead of PyPI:

```bash
uvx --from git+https://github.com/SanthaKumar-K-2004/linkedin-mcp-zero mcp-server-linkedin-zero --doctor
```

## One-Line Agent Setup

Claude Code:

```bash
claude mcp add linkedin-zero -- uvx mcp-server-linkedin-zero
```

Claude Desktop:

```bash
uvx mcp-server-linkedin-zero --install-client claude-desktop
```

Claude Desktop with browser/profile/feed tools enabled:

```bash
uvx mcp-server-linkedin-zero --install-client claude-desktop --with-extra browser
```

Cursor, run inside the project where you want `.cursor/mcp.json`:

```bash
uvx mcp-server-linkedin-zero --install-client cursor
```

Custom MCP clients:

```bash
uvx mcp-server-linkedin-zero
```

Streamable HTTP:

```bash
uvx mcp-server-linkedin-zero --transport streamable-http --host 127.0.0.1 --port 8000
```

GitHub-source agent setup:

```bash
claude mcp add linkedin-zero -- uvx --from git+https://github.com/SanthaKumar-K-2004/linkedin-mcp-zero mcp-server-linkedin-zero
```

## Safe Auto Config

The installer does not overwrite your whole MCP config. It:

- Finds the right config path for Claude Desktop or Cursor.
- Creates missing folders.
- Reads existing JSON.
- Preserves every other MCP server.
- Adds or updates only `linkedin-zero`.
- Uses the absolute `uvx` path so GUI apps do not fail on missing shell `PATH`.
- Adds `HOME` and a safe `PATH` to the MCP server environment.
- Creates a timestamped `.bak` backup before saving.
- If the current config JSON is broken, saves it as `.invalid.<timestamp>.bak`.
- Recovers from the latest valid backup when one exists.
- Writes JSON atomically.

Manual config:

```json
{
  "mcpServers": {
    "linkedin-zero": {
      "command": "uvx",
      "args": ["mcp-server-linkedin-zero"]
    }
  }
}
```

Print the config without editing files:

```bash
uvx mcp-server-linkedin-zero --print-config
```

Print a browser-enabled config:

```bash
uvx mcp-server-linkedin-zero --print-config --with-extra browser
```

## Platform Matrix

| Platform | Command |
|---|---|
| Claude Code | `claude mcp add linkedin-zero -- uvx mcp-server-linkedin-zero` |
| Claude Desktop | `uvx mcp-server-linkedin-zero --install-client claude-desktop` |
| Cursor | `uvx mcp-server-linkedin-zero --install-client cursor` |
| Custom stdio client | `uvx mcp-server-linkedin-zero` |
| HTTP client | `uvx mcp-server-linkedin-zero --transport streamable-http --port 8000` |
| Docker | Not required |
| Low-spec laptop | Supported, browser tools stay lazy |

## What `--doctor` Checks

```bash
uvx mcp-server-linkedin-zero --doctor
```

It detects:

- OS and Python version.
- Python executable.
- CPU count.
- Total and available RAM.
- Free disk.
- Local data directory.
- Chrome, Chromium, Brave, or Edge.
- CDP URL.
- Docker/display state.
- Optional packages: JobSpy, PyMuPDF, Playwright, Patchright.
- Recommended mode: `full`, `balanced`, or `lean`.

Example:

```json
{
  "python": "3.12.13",
  "cpu_count": 8,
  "ram_total_mb": 7135,
  "ram_available_mb": 2539,
  "chrome": "/usr/bin/google-chrome",
  "mode": "full",
  "notes": ["Browser tools need `uv sync --extra browser`."]
}
```

## Tool Inventory

| # | Tool | Engine | Risk | What it does |
|---|---|---|---|---|
| 1 | `search_jobs` | E1 | Zero | Search LinkedIn jobs |
| 2 | `search_jobs_multi` | E1 | Zero | Search LinkedIn, Indeed, Google, ZipRecruiter, Glassdoor |
| 3 | `get_job_details` | E1 | Zero | Full public job details |
| 4 | `get_company_jobs` | E1 | Zero | Public jobs at a company |
| 5 | `get_company_profile` | E1 | Zero | Company signals from public jobs |
| 6 | `search_companies` | E1 | Zero | Company search from job signals |
| 7 | `get_job_salary` | E1 | Zero | Salary extraction |
| 8 | `get_job_trends` | E1 | Zero | Role/location trend summary |
| 9 | `get_industry_insights` | E1 | Zero | Industry job insights |
| 10 | `search_jobs_advanced` | E1 | Zero | Search with filters |
| 11 | `analyze_resume` | RE | Zero | Parse TXT, MD, DOCX, optional PDF |
| 12 | `get_resume_insights` | RE | Zero | Skill gaps and suggestions |
| 13 | `match_jobs_to_resume` | ME | Zero | Rank jobs against resume |
| 14 | `compare_jobs` | ME | Zero | Compare 2-5 jobs |
| 15 | `export_jobs` | LO | Zero | CSV/JSON export |
| 16 | `save_job_alert` | ST | Zero | Save recurring search |
| 17 | `get_saved_alerts` | ST | Zero | List alerts |
| 18 | `check_saved_alerts` | E1+ST | Zero | Run alerts and find new matches |
| 19 | `get_my_profile` | E2 | Minimal | Read your profile through Chrome CDP |
| 20 | `get_person_profile` | E2 | Minimal | Read a public/person profile |
| 21 | `search_people` | E2 | Minimal | LinkedIn people search |
| 22 | `get_my_connections` | E2 | Minimal | Read connection list |
| 23 | `get_inbox` | E2 | Minimal | Read inbox list |
| 24 | `get_conversation` | E2 | Minimal | Read one thread |
| 25 | `get_feed` | E2 | Minimal | Read home feed |
| 26 | `get_notifications` | E2 | Minimal | Read notifications |
| 27 | `get_sidebar_profiles` | E2 | Minimal | Read sidebar suggestions |
| 28 | `get_company_employees` | E2 | Low | Read company people page |
| 29 | `check_session` | E2 | Minimal | Check Chrome/CDP readiness |
| 30 | `get_engine_status` | System | Zero | Runtime and engine status |
| 31 | `get_help` | System | Zero | Tool documentation |
| 32 | `get_profile_voyager` | E3 | Low | Gated off by default |

## Architecture

```text
Claude / Cursor / Custom Agent
        |
        | MCP stdio or Streamable HTTP
        v
┌──────────────────────────────────────────────────────────────┐
│ LinkedIn MCP Zero                                            │
│                                                              │
│  FastMCP tool layer  ->  32 compact tools                    │
│          |                                                   │
│          +-- E1 Public APIs      LinkedIn guest jobs         │
│          +-- Resume Engine       local TXT/MD/DOCX/PDF       │
│          +-- Matching Engine     local scoring               │
│          +-- Storage             SQLite + exports            │
│          +-- E2 Browser          real Chrome via CDP         │
│          +-- E3 Voyager          off by default              │
│                                                              │
│  Shared: cache, rate limit, config, autodetect, logging      │
└──────────────────────────────────────────────────────────────┘
```

## Hidden Gems Wired

| Hidden gem | Used for |
|---|---|
| LinkedIn Guest Jobs API | Zero-login public job search/details |
| JobSpy | Optional 5-board job search |
| JSON-LD Schema.org | Stable salary, skills, dates, job detail parsing |
| FastMCP | MCP server, schemas, stdio/HTTP transports |
| Chrome DevTools Protocol | Real Chrome read-only profile/feed/inbox tools |
| Patchright | Opt-in fallback when CDP is unavailable |
| python-docx + PyMuPDF | Local resume parsing |
| pydantic-settings | Type-safe environment config |
| structlog | Structured logs |

## Full-Power Local Mode

Clone and install everything:

```bash
git clone https://github.com/SanthaKumar-K-2004/linkedin-mcp-zero.git
cd linkedin-mcp-zero
uv sync --extra dev --extra multi --extra pdf --extra browser
```

Run checks:

```bash
uv run pytest
uv run ruff check .
uv run linkedin-mcp-zero --doctor
```

Run server:

```bash
uv run linkedin-mcp-zero
```

## Browser Tools

Important: `uvx` runs this MCP in an isolated Python environment. If Playwright is
installed globally, in Node, or in another virtual environment, this MCP will not
see it. Browser support must be installed in the MCP runtime with the `browser`
extra.

Install Claude Desktop config with browser extra:

```bash
uvx mcp-server-linkedin-zero --install-client claude-desktop --with-extra browser
```

Install Cursor config with browser extra:

```bash
uvx mcp-server-linkedin-zero --install-client cursor --with-extra browser
```

Start Chrome with CDP:

```bash
google-chrome --remote-debugging-port=9222
```

Then call:

```text
check_session
get_my_profile
search_people
get_feed
get_inbox
```

Opt-in Patchright fallback:

```bash
LINKEDIN_MCP_ENABLE_PATCHRIGHT_FALLBACK=true uvx mcp-server-linkedin-zero
```

## Optional Extras Guide

| Feature | Why status may show unavailable | Fix |
|---|---|---|
| Browser tools | Python Playwright is not installed inside `uvx` MCP runtime | `--with-extra browser` |
| Multi-board search | JobSpy is not installed inside `uvx` MCP runtime | `--with-extra multi` |
| PDF resume parsing | PyMuPDF is not installed inside `uvx` MCP runtime | `--with-extra pdf` |

Examples:

```bash
uvx mcp-server-linkedin-zero --install-client claude-desktop --with-extra browser
uvx mcp-server-linkedin-zero --install-client claude-desktop --with-extra multi
uvx mcp-server-linkedin-zero --install-client claude-desktop --with-extra pdf
```

Combine extras:

```bash
uvx mcp-server-linkedin-zero --install-client claude-desktop --with-extra browser --with-extra multi --with-extra pdf
```

For a local clone:

```bash
uv sync --extra browser --extra multi --extra pdf
uv run linkedin-mcp-zero --install-client claude-desktop
```

## Low-Spec Mode

No Docker. No always-on browser. No heavy services.

If RAM or disk is low, the server still works:

- Public job tools keep running.
- Resume tools stay local.
- Alerts use SQLite.
- Browser tools wait until called.
- Browser auto-unloads after idle time.
- Optional extras are skipped unless installed.

Quality is not reduced; only engine loading is smarter.

## Development And Release

Build:

```bash
uv build
```

Publish a new version:

```bash
uv publish
```

Publish the current `0.1.2` installer-recovery patch:

```bash
UV_PUBLISH_TOKEN="pypi-YOUR_NEW_TOKEN" uv publish dist/mcp_server_linkedin_zero-0.1.2*
```

Run from PyPI:

```bash
uvx mcp-server-linkedin-zero
```

Run from GitHub source:

```bash
uvx --from git+https://github.com/SanthaKumar-K-2004/linkedin-mcp-zero mcp-server-linkedin-zero
```

## Safety

This project intentionally avoids automated write actions. It does not apply to
jobs, send messages, create posts, connect with people, or modify your LinkedIn
account. Browser tools are read-only and require your own Chrome session.

Voyager is gated off by default because it is riskier than public APIs or real
browser reading.

## License

Apache 2.0. See [LICENSE](LICENSE).
