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

## Cursor

Run inside the project where you want `.cursor/mcp.json`:

```bash
uvx mcp-server-linkedin-zero --install-client cursor
```

The installer preserves existing MCP servers and creates a `.bak` backup.

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

Start Chrome with CDP:

```bash
google-chrome --remote-debugging-port=9222
```

Then call `check_session` from your MCP client.

## Low-Spec / No Docker

Docker is not required. Engine 1 public tools work on low-spec systems. Browser
tools are lazy and unload after idle time. Optional extras are installed only
when users need those features.
