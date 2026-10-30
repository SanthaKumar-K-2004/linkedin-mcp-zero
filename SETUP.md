# LinkedIn MCP Zero Setup

## Fastest Start

No Docker is required.

```bash
uvx linkedin-mcp-zero --doctor
```

Run the MCP server directly:

```bash
uvx linkedin-mcp-zero
```

## Claude Desktop

Install safely into Claude Desktop:

```bash
uvx --refresh-package linkedin-mcp-zero linkedin-mcp-zero --install-client claude-desktop
uvx --refresh-package linkedin-mcp-zero linkedin-mcp-zero --verify-client claude-desktop
```

Then fully quit and reopen Claude Desktop.

## Claude Code

Recommended one-command setup:

```bash
uvx --refresh-package linkedin-mcp-zero linkedin-mcp-zero --install-client claude-code
```

Manual equivalent:

```bash
claude mcp add linkedin-zero -- uvx --from linkedin-mcp-zero linkedin-mcp-zero
```

## Cursor

Run inside the project where you want `.cursor/mcp.json`:

```bash
uvx linkedin-mcp-zero --install-client cursor
uvx linkedin-mcp-zero --verify-client cursor
```

## VS Code

VS Code uses top-level `servers`, not `mcpServers`.

```bash
uvx linkedin-mcp-zero --install-client vscode
uvx linkedin-mcp-zero --verify-client vscode
```

## Google Antigravity

Install safely into Google Antigravity IDE & Agent Framework:

```bash
uvx linkedin-mcp-zero --install-client antigravity
uvx linkedin-mcp-zero --verify-client antigravity
```

This writes directly to `.agents/mcp_config.json` (workspace) or `~/.gemini/antigravity-ide/mcp_config.json` (global).

## Browser Mode

Browser/profile/feed/inbox tools are not enabled by default. They are read-only
but they use your logged-in browser session, so they carry account risk.

```bash
uvx linkedin-mcp-zero --install-client claude-desktop --with-extra browser
```

Start Chrome with CDP and log in manually:

```bash
google-chrome --remote-debugging-port=9222
```

Then call `check_session` from your MCP client.

Important: `uvx` is isolated. Global Python Playwright, Node Playwright, or
another project virtualenv does not count. Use `--with-extra browser` so the MCP
runtime gets its own browser dependencies.

## Token Usage

Claude Desktop does not expose built-in per-MCP token counts.

This server tracks usage safely:

- Estimated tokens: `ceil(response_chars / 4)`, always available.
- Exact-style counting: optional Anthropic `/v1/messages/count_tokens`.
- Full response payloads are not stored.
- Exact-style counting sends the counted response text to Anthropic only when
  both `ANTHROPIC_API_KEY` and `LINKEDIN_MCP_EXACT_TOKEN_COUNT=true` are set.

Enable exact-style counting:

```bash
ANTHROPIC_API_KEY=sk-ant-... LINKEDIN_MCP_EXACT_TOKEN_COUNT=true uvx linkedin-mcp-zero
```

Then ask your MCP client to call:

- `get_usage_stats`
- `get_tool_usage_summary`
- `reset_usage_stats`

Do not use terminal transcript logging as the main token counter; it can expose
private profile, inbox, and resume data.

## Optional Extras

```bash
# Browser/CDP tools
uvx linkedin-mcp-zero --install-client claude-desktop --with-extra browser

# Multi-board search through JobSpy
uvx linkedin-mcp-zero --install-client claude-desktop --with-extra multi

# PDF resume parsing through PyMuPDF
uvx linkedin-mcp-zero --install-client claude-desktop --with-extra pdf

# Everything
uvx linkedin-mcp-zero --install-client claude-desktop --with-extra browser --with-extra multi --with-extra pdf
```

## Safety Model

- Local tools: zero LinkedIn account risk.
- Public/no-login tools: read-only, no LinkedIn account required.
- Browser tools: opt-in read-only browser mode with account risk.
- Voyager/private API mode: disabled unless explicitly enabled.

No tool posts, likes, connects, follows, applies, or sends messages.

## Tool Counts

- Default: 29 usable tools.
- Browser enabled: 40 tools.
- Browser + Voyager enabled: 41 tools.

`search_jobs_multi` works in default mode by falling back to LinkedIn-only
results. Install `--with-extra multi` for all 5 job boards.

## Cloud Hosting & Docker Deployment

### 1. Pre-built Multi-Arch Container (GitHub Container Registry)

Run the pre-built, hardened multi-arch image directly:

```bash
docker run -d -p 8000:8000 \
  -e LINKEDIN_MCP_API_KEY="my-secret-key" \
  -e RATE_LIMIT_PER_MINUTE=120 \
  --name linkedin-mcp-zero \
  ghcr.io/santhakumar-k-2004/linkedin-mcp-zero:latest
```

### 2. Build Container Locally

```bash
# Build the Docker image
docker build -t linkedin-mcp-zero .

# Run container in Streamable HTTP mode
docker run -d -p 8000:8000 \
  -e LINKEDIN_MCP_API_KEY="my-secret-key" \
  -e RATE_LIMIT_PER_MINUTE=120 \
  linkedin-mcp-zero
```

### 3. 1-Click Online Cloud Hosting

| Platform | Deployment Instructions |
| :--- | :--- |
| **Render** | Connect repository and select Docker runtime, or use [`render.yaml`](file:///home/santhakumar/Documents/linkedin-mcp-zero/render.yaml) blueprint |
| **Railway** | Deploy with Railway CLI: `railway up` using [`railway.json`](file:///home/santhakumar/Documents/linkedin-mcp-zero/railway.json) |
| **Fly.io** | Deploy with Fly CLI: `fly launch` / `fly deploy` using [`fly.toml`](file:///home/santhakumar/Documents/linkedin-mcp-zero/fly.toml) |
| **Kubernetes** | Deploy cluster manifest: `kubectl apply -f deploy/k8s.yaml` |

## Streamable-HTTP, SSE & Remote AI Client Setup

When running in `streamable-http` mode, the server implements standard Starlette CORS headers, health checks at `/health`, and ASGI API-Key/Rate-limiting middleware:

*   **Authorization Header:** Requests must include `Authorization: Bearer <api-key>` or an `x-api-key: <api-key>` header.
*   **Rate Limiting:** Defaults to 120 requests per minute per IP, returning `HTTP 429 Too Many Requests` on violation.
*   **CORS:** Origins can be restricted by configuring `CORS_ALLOWED_ORIGINS` in the environment.

### Remote MCP Client Configuration (Claude Desktop, Cursor, Antigravity, VS Code)

Connect your remote AI client to your hosted instance (`https://your-service.onrender.com`):

```json
{
  "mcpServers": {
    "linkedin-remote": {
      "url": "https://your-service.onrender.com/sse",
      "headers": {
        "x-api-key": "my-secret-key"
      }
    }
  }
}
```

### Remote Health and Probe Verification

```bash
# Verify service health
curl -f https://your-service.onrender.com/health

# Verify tools discovery
curl -H "x-api-key: my-secret-key" https://your-service.onrender.com/
```

## Advanced MCP Spec Primitives

### 💬 MCP Sampling (LLM Delegation)
Using `ctx.sample()`, the server asks the client LLM to reason over gathered data. This enables advanced agent behaviors without hardcoding LLM clients/keys:
*   `smart_match_jobs`: Submits resume skills and listings, requesting Claude to rank jobs and identify skill gaps.
*   `generate_cover_letter`: Synthesizes a tailored, 200-word cover letter matching target requirements.
*   `analyze_salary_offer`: Evaluates salary structures against market data.

### ❓ MCP Elicitation (Interactive Input)
Using `ctx.elicit()`, tools can pause execution and prompt the user for structured, Pydantic-validated forms:
*   `personalized_job_hunt`: Interactively prompts for a `SearchPreferences` form containing min salary, max distance, must-have skills, and preferred company size.
*   `confirm_export`: Prompts for confirmation before initiating job exports.

