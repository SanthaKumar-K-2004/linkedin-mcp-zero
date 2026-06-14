# LinkedIn MCP Zero Setup

## Fastest Start

Run from PyPI:

```bash
uvx mcp-server-linkedin-zero --doctor
```

GitHub source fallback:

```bash
uvx --from git+https://github.com/SanthaKumar-K-2004/linkedin-mcp-zero mcp-server-linkedin-zero --doctor
```

## Claude Code

```bash
claude mcp add linkedin-zero -- uvx mcp-server-linkedin-zero
```

## Claude Desktop

```bash
uvx mcp-server-linkedin-zero --install-client claude-desktop
```

With browser/profile/feed tools:

```bash
uvx mcp-server-linkedin-zero --install-client claude-desktop --with-extra browser
```

## Cursor

Run inside the project where you want `.cursor/mcp.json`:

```bash
uvx mcp-server-linkedin-zero --install-client cursor
```

With browser/profile/feed tools:

```bash
uvx mcp-server-linkedin-zero --install-client cursor --with-extra browser
```

The installer:

- Preserves existing MCP servers.
- Uses the absolute `uvx` path for GUI app reliability.
- Adds `HOME` and a safe `PATH`.
- Creates a `.bak` backup before writing.
- If JSON is broken, saves it as `.invalid.<timestamp>.bak`.
- Recovers from the latest valid backup when possible.

## Manual Config

```json
{
  "mcpServers": {
    "linkedin-zero": {
      "command": "uvx",
      "args": [
        "mcp-server-linkedin-zero"
      ]
    }
  }
}
```

## Full Power Local Mode

Inside this repo:

```bash
uv sync --extra multi --extra pdf --extra browser
uv run linkedin-mcp-zero
```

## Browser Tools

`uvx` is isolated. Global Python Playwright, Node Playwright, and another
project's virtualenv Playwright do not count. Install the browser extra into the
MCP runtime:

```bash
uvx mcp-server-linkedin-zero --install-client claude-desktop --with-extra browser
```

Start Chrome with CDP:

```bash
google-chrome --remote-debugging-port=9222
```

Then call `check_session` from your MCP client.

## Optional Extras

```bash
# Browser/CDP tools
uvx mcp-server-linkedin-zero --install-client claude-desktop --with-extra browser

# Multi-board search through JobSpy
uvx mcp-server-linkedin-zero --install-client claude-desktop --with-extra multi

# PDF resume parsing through PyMuPDF
uvx mcp-server-linkedin-zero --install-client claude-desktop --with-extra pdf

# Everything
uvx mcp-server-linkedin-zero --install-client claude-desktop --with-extra browser --with-extra multi --with-extra pdf
```

## Low-Spec / No Docker

Docker is not required. Engine 1 public tools work on low-spec systems. Browser
tools are lazy and unload after idle time. Optional extras are installed only
when users need those features.

## Update Existing Installs

Refresh and reinstall the MCP config:

```bash
uvx --refresh-package mcp-server-linkedin-zero --from mcp-server-linkedin-zero mcp-server-linkedin-zero --install-client claude-desktop
```

Then fully restart Claude Desktop.
