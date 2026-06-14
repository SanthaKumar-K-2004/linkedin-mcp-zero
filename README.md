# LinkedIn MCP Zero

Zero-risk LinkedIn job intelligence for AI agents.

Public jobs, resume matching, alerts, exports, and optional read-only browser
tools in one MCP server. Built for Claude Code, Claude Desktop, Cursor, and any
MCP-compatible client.

```text
32 tools | public-first | no Docker required | low-RAM friendly | FastMCP
```

## What It Does

LinkedIn MCP Zero gives AI agents practical LinkedIn intelligence without making
dangerous write actions:

- Search public LinkedIn jobs without login.
- Fetch public job details, salary, skills, company, and posting metadata.
- Search multiple job boards through optional JobSpy.
- Parse resumes locally from TXT, MD, DOCX, and optional PDF.
- Match jobs to resumes with local scoring.
- Save job alerts in local SQLite.
- Export jobs to CSV or JSON.
- Use your real Chrome through CDP for optional read-only profile/feed/inbox tools.
- Report system health, RAM, disk, Python, Chrome, CDP, and optional packages.

## Quick Start

Use directly from GitHub before PyPI release:

```bash
uvx --from git+https://github.com/SanthaKumar-K-2004/linkedin-mcp-zero mcp-server-linkedin-zero --doctor
```

After PyPI release:

```bash
uvx mcp-server-linkedin-zero --doctor
```

Inside a local clone:

```bash
uv run linkedin-mcp-zero --doctor
```

## One-Line MCP Install

Claude Code:

```bash
claude mcp add linkedin-zero -- uvx --from git+https://github.com/SanthaKumar-K-2004/linkedin-mcp-zero mcp-server-linkedin-zero
```

Claude Desktop:

```bash
uvx --from git+https://github.com/SanthaKumar-K-2004/linkedin-mcp-zero mcp-server-linkedin-zero --install-client claude-desktop --package-source github
```

Cursor, run inside the project where you want `.cursor/mcp.json`:

```bash
uvx --from git+https://github.com/SanthaKumar-K-2004/linkedin-mcp-zero mcp-server-linkedin-zero --install-client cursor --package-source github
```

The installer safely merges only this entry:

```json
{
  "mcpServers": {
    "linkedin-zero": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/SanthaKumar-K-2004/linkedin-mcp-zero",
        "mcp-server-linkedin-zero"
      ]
    }
  }
}
```

It preserves existing MCP servers and writes a timestamped backup before saving.

## Platform Support

| Platform | Setup |
|---|---|
| Claude Code | `claude mcp add linkedin-zero -- uvx --from git+https://github.com/SanthaKumar-K-2004/linkedin-mcp-zero mcp-server-linkedin-zero` |
| Claude Desktop | `--install-client claude-desktop --package-source github` |
| Cursor | `--install-client cursor --package-source github` |
| Custom MCP client | stdio command: `uvx --from git+https://github.com/SanthaKumar-K-2004/linkedin-mcp-zero mcp-server-linkedin-zero` |
| HTTP clients | `uv run linkedin-mcp-zero --transport streamable-http --port 8000` |
| Docker | Not required |

## Smart System Detection

Run:

```bash
mcp-server-linkedin-zero --doctor
```

The server detects:

- OS and Python version.
- Python executable.
- CPU count.
- Total and available RAM.
- Free disk.
- Data directory.
- Chrome, Chromium, Brave, or Edge.
- CDP URL.
- Docker/display state.
- Optional packages: JobSpy, PyMuPDF, Playwright, Patchright.
- Recommended runtime mode: `full`, `balanced`, or `lean`.

Low-spec systems still work. The server does not reduce result quality. It only
keeps expensive engines lazy:

- Engine 1 public job tools stay lightweight.
- Local resume/storage/export tools stay lightweight.
- Browser tools load only when called.
- Browser connection unloads after idle time.
- Optional extras are installed only when users ask for those features.

## Tool Inventory

| # | Tool | Engine | Risk | Status |
|---|---|---|---|---|
| 1 | `search_jobs` | E1 | Zero | Working public LinkedIn guest search |
| 2 | `search_jobs_multi` | E1 | Zero | Optional JobSpy |
| 3 | `get_job_details` | E1 | Zero | Working public job details |
| 4 | `get_company_jobs` | E1 | Zero | Working public job inference |
| 5 | `get_company_profile` | E1 | Zero | Working public job-signal inference |
| 6 | `search_companies` | E1 | Zero | Working public job-signal inference |
| 7 | `get_job_salary` | E1 | Zero | Working from public job details |
| 8 | `get_job_trends` | E1 | Zero | Working aggregation |
| 9 | `get_industry_insights` | E1 | Zero | Working aggregation |
| 10 | `search_jobs_advanced` | E1 | Zero | Working public search |
| 11 | `analyze_resume` | RE | Zero | TXT, MD, DOCX; optional PDF |
| 12 | `get_resume_insights` | RE | Zero | Working local keyword insights |
| 13 | `match_jobs_to_resume` | ME | Zero | Working local scoring |
| 14 | `compare_jobs` | ME | Zero | Working comparison |
| 15 | `export_jobs` | LO | Zero | CSV/JSON export |
| 16 | `save_job_alert` | ST | Zero | SQLite storage |
| 17 | `get_saved_alerts` | ST | Zero | SQLite storage |
| 18 | `check_saved_alerts` | E1+ST | Zero | Public search + SQLite |
| 19 | `get_my_profile` | E2 | Minimal | Chrome CDP read-only |
| 20 | `get_person_profile` | E2 | Minimal | Chrome CDP read-only |
| 21 | `search_people` | E2 | Minimal | Chrome CDP read-only |
| 22 | `get_my_connections` | E2 | Minimal | Chrome CDP read-only |
| 23 | `get_inbox` | E2 | Minimal | Chrome CDP read-only |
| 24 | `get_conversation` | E2 | Minimal | Chrome CDP read-only |
| 25 | `get_feed` | E2 | Minimal | Chrome CDP read-only |
| 26 | `get_notifications` | E2 | Minimal | Chrome CDP read-only |
| 27 | `get_sidebar_profiles` | E2 | Minimal | Chrome CDP read-only |
| 28 | `get_company_employees` | E2 | Low | Chrome CDP read-only |
| 29 | `check_session` | E2 | Minimal | CDP readiness check |
| 30 | `get_engine_status` | System | Zero | Working |
| 31 | `get_help` | System | Zero | Working |
| 32 | `get_profile_voyager` | E3 | Low | Gated off by default |

## Optional Full-Power Mode

Inside a local clone:

```bash
uv sync --extra multi --extra pdf --extra browser
```

Extras:

- `multi`: JobSpy multi-board search.
- `pdf`: PyMuPDF PDF resume parsing.
- `browser`: Playwright CDP and Patchright fallback support.

Browser tools:

```bash
google-chrome --remote-debugging-port=9222
```

Then call `check_session` from your MCP client.

## How It Works

```text
AI client
  |
  | MCP stdio / Streamable HTTP
  v
FastMCP server
  |
  +-- Engine 1: public LinkedIn jobs API, no login
  +-- Resume engine: local parsing
  +-- Matching engine: local scoring
  +-- Storage: local SQLite and exports
  +-- Engine 2: real Chrome via CDP, read-only
  +-- Engine 3: Voyager, gated off by default
```

Hidden gems wired:

- LinkedIn Guest Jobs API.
- JobSpy optional multi-board search.
- JSON-LD Schema.org parsing.
- FastMCP.
- Chrome DevTools Protocol.
- Patchright opt-in fallback.
- python-docx and optional PyMuPDF.
- pydantic-settings.
- structlog.

## Development

```bash
git clone https://github.com/SanthaKumar-K-2004/linkedin-mcp-zero.git
cd linkedin-mcp-zero
uv sync --extra dev
uv run pytest
uv run ruff check .
```

Build:

```bash
uv build
```

Publish to PyPI, after configuring credentials:

```bash
uv publish
```

After PyPI release, users can use the shorter command:

```bash
uvx mcp-server-linkedin-zero
```

## License

Apache 2.0.
