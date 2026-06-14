# LinkedIn MCP Zero Implementation Plan

## Current Status

The repository now contains a runnable Python package with all 32 tools
registered in FastMCP. Engine 1, local resume, local matching, storage, export,
status, and help paths are connected. Browser and Voyager tools are registered
with explicit connection/risk gating.

## Phase 1: Foundation + Engine 1

- [x] Initialize `pyproject.toml`, package entry points, README, env example
- [x] Create `src/linkedin_mcp_zero` package structure
- [x] Add settings, defaults, runtime autodetect
- [x] Add structured logging, error types, compression helpers
- [x] Add TTL cache and token-bucket pacing
- [x] Add public LinkedIn guest API client
- [x] Add JSON-LD and BeautifulSoup parsing for job detail pages
- [x] Register MCP tools: `search_jobs`, `search_jobs_advanced`,
      `get_job_details`, `get_job_salary`, `get_company_jobs`,
      `get_engine_status`
- [x] Add parser tests
- [x] Add richer company search/profile tools
- [x] Register all 32 planned MCP tools
- [x] Add MCP app registration smoke checks
- [ ] Add first-run safety/disclaimer text

## Phase 2: Multi-Board + Resume

- [x] Add optional `python-jobspy` wrapper for `search_jobs_multi`
- [x] Add resume parsing for TXT/MD/DOCX, optional PDF
- [x] Add local resume storage
- [x] Add local matching baseline
- [ ] Add LLM provider abstraction for resume insights and matching

## Phase 3: Browser Engine

- [x] Add CDP connection detection
- [x] Register read-only profile/session tools
- [x] Add Playwright DOM extractors for E2 tools
- [x] Add browser auto-unload
- [x] Add opt-in Patchright fallback launch when CDP is unavailable

## Phase 4: Release Hardening

- [ ] Add full docs for Claude Desktop, Claude Code, Cursor, and HTTP usage
- [ ] Add Docker image for Engine 1
- [ ] Add CI checks
- [ ] Add PyPI release workflow
