# LinkedIn MCP Zero Setup

## Fastest Start

No Docker is required.

```bash
uvx mcp-server-linkedin-zero --doctor
```

Run the MCP server directly:

```bash
uvx mcp-server-linkedin-zero
```

## Claude Desktop

Install safely into Claude Desktop:

```bash
uvx --refresh-package mcp-server-linkedin-zero mcp-server-linkedin-zero --install-client claude-desktop
uvx --refresh-package mcp-server-linkedin-zero mcp-server-linkedin-zero --verify-client claude-desktop
```

Then fully quit and reopen Claude Desktop.

## Claude Code

Recommended one-command setup:

```bash
uvx --refresh-package mcp-server-linkedin-zero mcp-server-linkedin-zero --install-client claude-code
```

Manual equivalent:

```bash
claude mcp add linkedin-zero -- uvx --from mcp-server-linkedin-zero mcp-server-linkedin-zero
```

## Cursor

Run inside the project where you want `.cursor/mcp.json`:

```bash
uvx mcp-server-linkedin-zero --install-client cursor
uvx mcp-server-linkedin-zero --verify-client cursor
```

## VS Code

VS Code uses top-level `servers`, not `mcpServers`.

```bash
uvx mcp-server-linkedin-zero --install-client vscode
uvx mcp-server-linkedin-zero --verify-client vscode
```

## Browser Mode

Browser/profile/feed/inbox tools are not enabled by default. They are read-only
but they use your logged-in browser session, so they carry account risk.

```bash
uvx mcp-server-linkedin-zero --install-client claude-desktop --with-extra browser
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
ANTHROPIC_API_KEY=sk-ant-... LINKEDIN_MCP_EXACT_TOKEN_COUNT=true uvx mcp-server-linkedin-zero
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
uvx mcp-server-linkedin-zero --install-client claude-desktop --with-extra browser

# Multi-board search through JobSpy
uvx mcp-server-linkedin-zero --install-client claude-desktop --with-extra multi

# PDF resume parsing through PyMuPDF
uvx mcp-server-linkedin-zero --install-client claude-desktop --with-extra pdf

# Everything
uvx mcp-server-linkedin-zero --install-client claude-desktop --with-extra browser --with-extra multi --with-extra pdf
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

## Docker Deployment (Engine 1)

You can build and run Engine 1 as a Docker container:

```bash
# Build the Docker image
docker build -t linkedin-mcp-zero .

# Run the container exposing port 8000 in HTTP mode
docker run -d -p 8000:8000 \
  -e LINKEDIN_MCP_API_KEY="my-secret-key" \
  -e LINKEDIN_MCP_RATE_LIMIT="100/minute" \
  linkedin-mcp-zero
```

## Streamable-HTTP & REST API Usage

When running in `streamable-http` mode, the server implements standard Starlette CORS headers and an ASGI API-Key/Rate-limiting middleware:

*   **Authorization Header:** Requests must include `Authorization: Bearer <api-key>` or an `x-api-key: <api-key>` header.
*   **Rate Limiting:** Defaults to 100 requests per minute per IP, returning `HTTP 429 Too Many Requests` on violation.
*   **CORS:** Origins can be restricted by configuring the `cors_allowed_origins` parameter in the environment.

Example request using `curl`:

```bash
curl -X POST http://localhost:8000/mcp/v1/tools/search_jobs \
  -H "Authorization: Bearer my-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"kw": "python", "limit": 5}'
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

