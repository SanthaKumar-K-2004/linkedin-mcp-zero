# LINKEDIN MCP ZERO — COMPLETE ARCHITECTURE & BUILD PLAN

> **Author:** Santhakumar K — Developer & Architect
> **Status:** Final Design Document v2.0
> **Goal:** Production-ready, zero-ban-risk, token-optimized LinkedIn MCP Server

---

## 📋 TABLE OF CONTENTS

1. [PROJECT VISION & PHILOSOPHY](#1-project-vision--philosophy)
2. [TOKEN OPTIMIZATION STRATEGY](#2-token-optimization-strategy)
3. [AUTO-CONFIGURATION SYSTEM](#3-auto-configuration-system)
4. [UNIVERSAL CONNECTIVITY LAYER](#4-universal-connectivity-layer)
5. [OPEN-SOURCE GEMS WE COMBINE](#5-open-source-gems-we-combine)
6. [THREE-ENGINE ARCHITECTURE](#6-three-engine-architecture)
7. [COMPLETE TOOL INVENTORY WITH RISK LABELS](#7-complete-tool-inventory-with-risk-labels)
8. [TOKEN BUDGET PER TOOL](#8-token-budget-per-tool)
9. [MODULE STRUCTURE](#9-module-structure)
10. [DATA FLOW & PROTOCOL](#10-data-flow--protocol)
11. [RESOURCE USAGE BUDGET](#11-resource-usage-budget)
12. [ERROR HANDLING & RECOVERY](#12-error-handling--recovery)
13. [PHASED BUILD PLAN](#13-phased-build-plan)

---

## 1. PROJECT VISION & PHILOSOPHY

### 1.1 The Core Problem We Solve

Existing LinkedIn MCP servers have fundamental flaws:
- **stickerdaniel/linkedin-mcp-server**: 2.3k★, but requires full browser, ~300MB RAM always, write tools buggy, no job matching, **high token usage** because every tool spins up browser
- **Other MCP servers**: All require browser automation, high resource usage, no token optimization

### 1.2 Our Philosophy

> **"Zero risk for reading. Manual for writing. Token-minimal always."**

| Principle | Implementation |
|-----------|---------------|
| 🟢 Zero ban risk | Public LinkedIn Guest API for all job/company features — no account needed |
| ⚡ Token minimal | Short tool names, compressed output, smart caching, browser only when needed |
| 🤖 Auto-configure | Detect OS, Python version, Chrome, APIs — zero manual config |
| 🔌 Universal | One config works for Claude Desktop, Claude Code, Cursor, custom agents |
| 🧠 Powerful matching | AI resume-to-job matching with configurable LLM provider |
| 💾 Lightweight | ~25MB idle, browser loads only on demand, auto-unloads |

### 1.3 The Hidden Gems We Combine

```
Gem 1: LinkedIn Guest Jobs API
├── URL: https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
├── Source: Public endpoint (reverse-engineered, used by Apify/ScrapingBee)
├── Why: ZERO risk — no login, no browser, no cookies
└── Our use: All job search tools

Gem 2: JobSpy Library
├── URL: https://github.com/speedyapply/JobSpy
├── Stars: 3,500+ | License: MIT
├── Why: Scrapes 5 job boards SIMULTANEOUSLY (LinkedIn, Indeed, Google, ZipRecruiter, Glassdoor)
└── Our use: Multi-platform job search in one function call

Gem 3: JSON-LD Schema.org Parsing
├── URL: https://schema.org/JobPosting
├── Why: LinkedIn embeds structured job data in every job page — most stable format
└── Our use: Salary extraction, skill parsing, job details

Gem 4: FastMCP Framework
├── URL: https://github.com/jlowin/fastmcp
├── Why: Fastest MCP server framework, auto-schema generation, async by default
└── Our use: MCP protocol layer

Gem 5: Chrome DevTools Protocol (CDP)
├── URL: https://chromedevtools.github.io/devtools-protocol/
├── Why: Connect to user's REAL Chrome — LinkedIn sees IDENTICAL signals to human
└── Our use: Profile viewing (Engine 2)

Gem 6: Patchright (Anti-detection Playwright fork)
├── URL: https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python
├── Why: Patches all Playwright detection vectors
└── Our use: Fallback browser when CDP unavailable

Gem 7: open-linkedin-api (Voyager API wrapper)
├── URL: https://github.com/linkedin-api/linkedin-api (Tom Quirk's library)
├── Why: Pure HTTP LinkedIn access — NO browser needed
└── Our use: Optional lightweight profile access (OFF by default)

Gem 8: python-docx + PyMuPDF
├── URL: https://github.com/python-openxml/python-docx / https://github.com/pymupdf/PyMuPDF
├── Why: Industry-standard resume parsing, 100% local
└── Our use: Zero-risk resume analysis

Gem 9: pydantic-settings
├── URL: https://github.com/pydantic/pydantic-settings
├── Why: Type-safe config from env vars + .env files + CLI args
└── Our use: Auto-configuration system

Gem 10: structlog
├── URL: https://github.com/hynek/structlog
├── Why: Structured logging, PII redaction built-in
└── Our use: Secure, debuggable logging
```

---

## 2. TOKEN OPTIMIZATION STRATEGY

This is **critical**. Claude Desktop users have limited token contexts. Every token our server wastes is a token the user can't use for their actual work.

### 2.1 Token Optimization Principles

```yaml
principle_1_compress_outputs:
  - "Use short field names: 'title' not 'job_title', 'co' not 'company_name'"
  - "No verbosity option — always return minimal viable data"
  - "Strip whitespace, null fields, redundant metadata"
  - "Example: {'title':'Sr Python Dev','co':'Google','loc':'remote','sal':'$150-200k','score':96}"

principle_2_smart_pagination:
  - "Default limit: 10 results (not 25)"
  - "User can request more: limit parameter up to 50"
  - "Always include total_count so user knows if more available"
  - "Token cost for 10 jobs: ~500 tokens vs ~1500 for 50"

principle_3_response_caching:
  - "Cache identical requests for 5 minutes (TTL)"
  - "Same search within 5 min = cache hit = ZERO tokens used"
  - "Cache key = hash(tool_name + params)"
  - "Token saved: 100% for cache hits"

principle_4_lazy_browser_loading:
  - "Browser (Engine 2) loads ONLY when user calls a browser tool"
  - "After 5min idle → auto-unload → frees ~300MB RAM"
  - "Tool calls while browser idle cost ~700 tokens vs ~50 for Engine 1"

principle_5_minimal_tool_names:
  - "Short tool names: 'search_jobs' not 'search_for_linkedin_jobs'"
  - "Short parameter names: 'kw' not 'keywords', 'loc' not 'location'"
  - "Tool description: one line, not paragraphs"
  - "MCP schema size: 2KB vs 10KB for verbose naming"

principle_6_streaming_capable:
  - "Large result sets returned as iterable (MCP streaming)"
  - "User sees first results while rest load"
  - "Can stop early if satisfied — no wasted tokens"

principle_7_batched_llm_calls:
  - "Match multiple jobs in ONE LLM call, not one per job"
  - "Batch size: up to 20 jobs per LLM call"
  - "Token saved: ~90% vs individual calls"
```

### 2.2 Token Cost Comparison

```yaml
scenario_search_jobs_10_results:
  verbose_server:
    tool_setup: 250 tokens  # Long names, long descriptions
    api_call: 50 tokens
    response: 1500 tokens  # Verbose field names, full HTML
    total: ~1800 tokens
  
  optimized_server:
    tool_setup: 80 tokens  # Short names, one-line descriptions
    api_call: 50 tokens
    response: 500 tokens  # Compressed fields, no nulls
    total: ~630 tokens
  
  savings: "~65% fewer tokens"

scenario_match_jobs_20_jobs:
  naive_server:
    llm_calls: 20 calls × 500 tokens = 10000 tokens
  
  optimized_server:
    llm_calls: 1 batched call × 1200 tokens = 1200 tokens
  
  savings: "~88% fewer tokens"

scenario_browser_profile_view:
  always_on_browser:
    browser_startup: 700 tokens  # Init message to Claude
    page_load: 600 tokens  # DOM content
    extract: 800 tokens  # Profile data
    total: ~2100 tokens
  
  lazy_browser:
    browser_load: 0 tokens (already loaded if active)
    page_load: 600 tokens
    extract: 300 tokens  # Compressed profile
    total: ~900 tokens (or 700 + 900 if cold start)
  
  savings: "~57% fewer tokens (warm) or ~24% (cold)"

scenario_full_pipeline_resume_to_matches:
  naive:
    analyze_resume: 800 tokens  # Verbose output
    search_jobs: 1800 tokens  # 25 results verbose
    match_jobs (per job): 20 × 800 tokens = 16000 tokens
    export: 500 tokens
    total: ~19100 tokens
  
  optimized:
    analyze_resume: 300 tokens  # Compressed output
    search_jobs: 630 tokens  # 10 results compressed
    match_jobs (batched): 1 call × 1500 tokens
    export: 100 tokens
    total: ~2530 tokens
  
  savings: "~87% fewer tokens — from 19100 to 2530"
```

### 2.3 Token-Saving Implementation Details

```python
# EXAMPLE: Compressed output vs verbose output

# VERBOSE (BAD) — ~1500 tokens for 10 jobs
[
    {
        "job_title": "Senior Python Developer",
        "company_name": "Google",
        "company_location": "Mountain View, California, United States",
        "salary_range": {
            "minimum_amount": 150000,
            "maximum_amount": 200000,
            "currency": "USD",
            "interval": "YEAR"
        },
        "job_description": "... 500 words ...",
        "job_url": "https://www.linkedin.com/jobs/view/123456789",
        "date_posted": "2026-06-10T14:30:00Z",
        "employment_type": "FULL_TIME",
        "seniority_level": "Mid-Senior level",
        "job_function": "Engineering",
        "industries": ["Internet", "Software Development"],
        ...
    }
]

# COMPRESSED (GOOD) — ~500 tokens for 10 jobs
[
    {
        "t": "Sr Python Developer",   # title
        "co": "Google",                # company
        "loc": "Mountain View, CA",    # location (shortened)
        "sal": "$150-200K/yr",         # salary (single string)
        "desc": "We're looking for...",# description (truncated 200 chars)
        "url": "https://lnkd.in/j/123",# url (shortened)
        "age": "2d",                   # date (relative, shortened)
        "type": "FT"                   # employment type (abbreviated)
    }
]
```

---

## 3. AUTO-CONFIGURATION SYSTEM

### 3.1 What We Auto-Detect

```yaml
auto_detect:
  os:
    - Windows: "Detect via platform.system()"
    - macOS: "Detect via platform.system()"
    - Linux: "Detect via platform.system()"
    - Action: Set default paths, browser detection strategy, line endings
  
  python:
    - version: "sys.version_info — warn if < 3.10"
    - executable: "sys.executable"
    - Action: Use sys.executable for uv/pip commands

  chrome:
    - windows: "C:\Program Files\Google\Chrome\Application\chrome.exe"
    - macos: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    - linux: "/usr/bin/google-chrome"
    - fallback: "which google-chrome || which chromium || which brave"
    - cdp_status: "Check http://127.0.0.1:9222/json/version"
    - Action: Auto-select CDP if available, else Patchright

  linkedin_session:
    - check: "~/.linkedin-mcp/profile/Default/Cookies"
    - Action: Warn if no session exists, guide user through --login

  llm_provider:
    - check: "OPENAI_API_KEY env var"
    - check: "ANTHROPIC_API_KEY env var"
    - check: "OLLAMA_HOST env var (default http://localhost:11434)"
    - Action: Auto-select available provider, fall back to none (disable matching)
  
  proxy:
    - check: "HTTP_PROXY / HTTPS_PROXY env vars"
    - Action: Auto-configure httpx to use proxy if set

  config_files:
    - check: ".env in CWD"
    - check: "~/.linkedin-mcp-zero/.env"
    - check: "~/.config/linkedin-mcp-zero/config.toml"
    - Action: Load in priority order, CLI args override all
```

### 3.2 Zero-Config Setup Flow

```
User runs: uvx linkedin-mcp-zero@latest
                │
                ▼
┌─────────────────────────────────────────┐
│ Auto-Configuration Engine                │
│                                         │
│ 1. Detect OS → Windows/macOS/Linux      │
│ 2. Detect Python → 3.13.3 ✅            │
│ 3. Detect Chrome → /usr/bin/chromium ✅ │
│ 4. Check CDP → port 9222... FOUND ✅    │
│ 5. Check LinkedIn session → EXISTS ✅   │
│ 6. Check LLM keys → OPENAI ✅           │
│ 7. Check proxy → NONE (direct)          │
│ 8. Check .env → FOUND ✅                │
│                                         │
│ ✓ All systems go!                       │
│ ✓ Engine 1 (Public APIs): Available     │
│ ✓ Engine 2 (CDP Browser): Available     │
│ ✓ Engine 3 (Voyager): OFF (by default)  │
│ ✓ Resume matching: Available (OpenAI)   │
└─────────────────────────────────────────┘
```

### 3.3 Configuration Priority

```yaml
priority_1_cli_args:
  - "--transport stdio"
  - "--log-level DEBUG"
  - "--timeout 10000"
  - "--enable-voyager"  # Must be explicit

priority_2_env_vars:
  - "OPENAI_API_KEY"
  - "ANTHROPIC_API_KEY"
  - "LINKEDIN_USER_DATA_DIR"
  - "CHROME_PATH"
  - "HTTP_PROXY"

priority_3_dot_env:
  - ".env in current directory"
  - "~/.linkedin-mcp-zero/.env"
  - "~/.config/linkedin-mcp-zero/.env"

priority_4_defaults:
  - "All defaults from config/defaults.py"
```

---

## 4. UNIVERSAL CONNECTIVITY LAYER

### 4.1 One Config Works Everywhere

```yaml
claude_desktop:
  config_location: "~/Library/Application Support/Claude/claude_desktop_config.json"
  transport: stdio
  config:
    json: {
      "mcpServers": {
        "linkedin-zero": {
          "command": "uvx",
          "args": ["linkedin-mcp-zero@latest"]
        }
      }
    }
  notes: |
    - Works immediately — no .env needed for Engine 1
    - For Engine 2 (browser): launch Chrome with --remote-debugging-port=9222
    - For resume matching: set OPENAI_API_KEY in .env or env vars

claude_code:
  config_command: "claude mcp add linkedin-zero -e \"uvx linkedin-mcp-zero@latest\""
  transport: stdio
  notes: |
    - Claude Code auto-manages stdio MCP servers
    - Can pass env vars inline: OPENAI_API_KEY=sk-... claude

cursor:
  config_location: ".cursor/mcp.json in project root"
  transport: stdio
  config:
    json: {
      "mcpServers": {
        "linkedin-zero": {
          "command": "uvx",
          "args": ["linkedin-mcp-zero@latest"]
        }
      }
    }
  notes: "Same config as Claude Desktop"

custom_python_agent:
  code: |
    import asyncio
    from mcp import ClientSession, StdioServerParameters
    
    async def main():
        params = StdioServerParameters(
            command="uvx",
            args=["linkedin-mcp-zero@latest"]
        )
        async with ClientSession(params) as session:
            result = await session.call_tool("search_jobs", {
                "kw": "Python developer",
                "loc": "remote"
            })
            print(result.content)
    
    asyncio.run(main())
  notes: "Full MCP protocol compatibility"

custom_js_agent:
  code: |
    import { Client } from "@modelcontextprotocol/sdk/client/index.js";
    import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
    
    const transport = new StdioClientTransport({
      command: "uvx",
      args: ["linkedin-mcp-zero@latest"]
    });
    
    const client = new Client({ name: "my-agent" });
    await client.connect(transport);
    const result = await client.request({
      method: "tools/call",
      params: { name: "search_jobs", arguments: { kw: "Python developer", loc: "remote" } }
    });

http_mode_web_clients:
  command: "uvx linkedin-mcp-zero@latest --transport streamable-http --port 8080"
  notes: |
    - Used by web-based MCP clients
    - FastMCP supports HTTP transport natively
    - Add --host 0.0.0.0 for Docker/network access
  
docker:
  config:
    json: {
      "mcpServers": {
        "linkedin-zero": {
          "command": "docker",
          "args": ["run", "--rm", "-i", "-p", "8080:8000", "santhakumar/linkedin-mcp-zero:latest"]
        }
      }
    }
  notes: |
    - Docker includes Engine 1 only (zero risk)
    - For Engine 2: mount Chrome socket via volume
    - For Engine 3: not recommended in Docker
```

### 4.2 Auto-Detect Client Type

```python
# At startup, server detects how it's being used
async def detect_client_environment():
    """Detect client and environment for optimal configuration."""
    
    # Check transport
    if os.environ.get('MCP_TRANSPORT') == 'streamable-http':
        client_type = 'http'
    else:
        client_type = 'stdio'
    
    # Check stdin for IDE signatures
    if 'VSCODE' in os.environ:
        client_env = 'vscode'
    elif 'CURSOR' in os.environ:
        client_env = 'cursor'
    elif 'WINDOWID' not in os.environ:  # No display = likely Claude Code
        client_env = 'cli'
    else:
        client_env = 'desktop'
    
    # Check if running inside Claude Desktop (via MCPB)
    if os.path.exists('/etc/claude'):  # Claude Desktop Docker detection
        client_env = 'claude_desktop'
    
    return {
        'transport': client_type,
        'environment': client_env,
        'is_docker': os.path.exists('/.dockerenv'),
        'has_display': 'DISPLAY' in os.environ or 'WAYLAND' in os.environ,
        'python_version': sys.version,
    }
```

---

## 5. OPEN-SOURCE GEMS WE COMBINE

### 5.1 Direct Dependencies (PyPI)

| Package | Version | Purpose | License | Stars | URL |
|---------|---------|---------|---------|-------|-----|
| `fastmcp` | ≥1.0 | MCP server framework | MIT | 5k+ | https://github.com/jlowin/fastmcp |
| `httpx` | ≥0.28 | Async HTTP client | BSD-3 | 13k+ | https://github.com/encode/httpx |
| `beautifulsoup4` | ≥4.12 | HTML parsing | MIT | — | https://www.crummy.com/software/BeautifulSoup/ |
| `lxml` | ≥5.3 | Fast HTML parser | BSD-3 | — | https://github.com/lxml/lxml |
| `python-jobspy` | ≥1.1 | Multi-platform job scraping | MIT | 3.5k+ | https://github.com/speedyapply/JobSpy |
| `python-docx` | ≥1.1 | .docx resume parsing | MIT | 4k+ | https://github.com/python-openxml/python-docx |
| `PyMuPDF` | ≥1.25 | .pdf resume parsing | AGPL | 5k+ | https://github.com/pymupdf/PyMuPDF |
| `pydantic-settings` | ≥2.7 | Config management | MIT | — | https://github.com/pydantic/pydantic-settings |
| `pydantic` | ≥2.10 | Data validation | MIT | 20k+ | https://github.com/pydantic/pydantic |
| `structlog` | ≥24.4 | Structured logging | Apache 2.0 | 3k+ | https://github.com/hynek/structlog |
| `rich` | ≥13.9 | CLI formatting | MIT | 50k+ | https://github.com/Textualize/rich |
| `platformdirs` | ≥4.3 | Cross-platform data dirs | MIT | 1k+ | https://github.com/platformdirs/platformdirs |

### 5.2 Optional Dependencies

| Package | Purpose | Condition |
|---------|---------|-----------|
| `playwright` | CDP browser connection | Engine 2 use only |
| `patchright` | Anti-detection browser fallback | Engine 2 when CDP unavailable |
| `openai` | LLM provider (GPT matching) | Resume matching with OpenAI |
| `anthropic` | LLM provider (Claude matching) | Resume matching with Anthropic |
| `open-linkedin-api` | Voyager API access | Engine 3 (OFF by default) |

### 5.3 Inspirations (Not Direct Dependencies)

```yaml
stickerdaniel/linkedin-mcp-server:
  url: https://github.com/stickerdaniel/linkedin-mcp-server
  stars: 2300
  what_we_borrow:
    - "FastMCP framework selection"
    - "Patchright integration pattern"
    - "Persistent browser profile management"
    - "Tool structure and error handling patterns"
  what_we_fix:
    - "Always-on browser → lazy-load + auto-unload"
    - "Browser-only job search → Public API (zero risk)"
    - "Patchright only → CDP + Patchright fallback"
    - "No token optimization → compressed outputs"
    - "Write tools (buggy) → removed entirely"

speedyapply/JobSpy:
  url: https://github.com/speedyapply/JobSpy
  stars: 3500
  what_we_borrow:
    - "Multi-platform job search engine"
    - "LinkedIn Guest API integration"
    - "Indeed/Google/Glassdoor/ZipRecruiter scrapers"
    - "Salary normalization logic"
  what_we_add:
    - "MCP tool wrapper"
    - "Integration with resume matching pipeline"
    - "Token-optimized output formatting"

linkedin-api/linkedin-api (Tom Quirk):
  url: https://github.com/tomquirk/linkedin-api
  stars: 7200
  what_we_borrow:
    - "Voyager API endpoint patterns"
    - "Session cookie auth approach"
    - "Profile parsing logic"
  what_we_change:
    - "Wrapped as MCP tool with DISABLED_BY_DEFAULT flag"
    - "Added explicit ban risk warning"
    - "Rate-limited to 20 calls/day"

fastmcp:
  url: https://github.com/jlowin/fastmcp
  docs: https://fastmcp.com
  what_we_borrow:
    - "Full MCP protocol implementation"
    - "Auto-schema generation from type hints"
    - "Stdio + Streamable HTTP transport"
    - "Tool discovery and registration"
```

---

## 6. THREE-ENGINE ARCHITECTURE

### 6.1 Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                                    │
│  USER'S ENVIRONMENT                                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐                   │
│  │ Claude       │  │ Claude       │  │ Cursor       │  │ Custom Agent          │                   │
│  │ Desktop      │  │ Code         │  │ (IDE)        │  │ (Python/JS/any)       │                   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘                   │
│         │                 │                 │                     │                                │
│         └─────────────────┴─────────────────┴─────────────────────┘                                │
│                                    │  MCP Protocol (stdio/HTTP)                                    │
│                                    ▼                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                           LINKEDIN MCP ZERO SERVER                                           │  │
│  │                                                                                              │  │
│  │  ┌────────────────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │  AUTO-CONFIG LAYER                                                                     │  │  │
│  │  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐  │  │  │
│  │  │  │ OS Detect │ │ Python    │ │ Chrome    │ │ LinkedIn  │ │ LLM Provider│ │ Proxy     │  │  │  │
│  │  │  │           │ │ Detect    │ │ Detect    │ │ Session   │ │ Detect    │ │ Detect    │  │  │  │
│  │  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘  │  │  │
│  │  └────────────────────────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                                              │  │
│  │  ┌────────────────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │  TOKEN-OPTIMIZED MCP LAYER (FastMCP)                                                    │  │  │
│  │  │  • Short tool names: search_jobs, get_job, match_jobs                                    │  │  │
│  │  │  • Compressed output: {'t':'Sr Py Dev','co':'Google','loc':'remote'}                    │  │  │
│  │  │  • Streaming responses: first 5 results fast, rest in background                        │  │  │
│  │  │  • Cache layer: identical requests → instant response (zero tokens)                     │  │  │
│  │  └────────────────────────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                                              │  │
│  │  ┌────────────────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │  SMART ENGINE SELECTOR                                                                  │  │  │
│  │  │  ┌──────────────┬─────────────────────────────────┬────────────────┐                   │  │  │
│  │  │  │ Tool Called   │ Engine Selected                  │ Risk Level     │                   │  │  │
│  │  │  ├──────────────┼─────────────────────────────────┼────────────────┤                   │  │  │
│  │  │  │ search_jobs  │ Engine 1: Public API             │ 🟢 ZERO        │                   │  │  │
│  │  │  │ get_job      │ Engine 1: Public API             │ 🟢 ZERO        │                   │  │  │
│  │  │  │ search_multi │ Engine 1: JobSpy                 │ 🟢 ZERO        │                   │  │  │
│  │  │  │ analyze_res  │ Resume Engine: Local parsing     │ 🟢 ZERO        │                   │  │  │
│  │  │  │ match_jobs   │ Matching Engine: LLM batch       │ 🟢 ZERO        │                   │  │  │
│  │  │  │ get_profile  │ Engine 2: CDP Browser            │ 🟢 MINIMAL     │                   │  │  │
│  │  │  │ get_inbox    │ Engine 2: CDP Browser            │ 🟢 MINIMAL     │                   │  │  │
│  │  │  │ voyager_prof │ Engine 3: Voyager API (OFF→)     │ 🟡 LOW         │                   │  │  │
│  │  │  └──────────────┴─────────────────────────────────┴────────────────┘                   │  │  │
│  │  └────────────────────────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                                              │  │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌──────────────┐  ┌──────────────────────┐        │  │  │
│  │  │  ENGINE 1    │  │  ENGINE 2        │  │  ENGINE 3    │  │  RESUME ENGINE       │        │  │  │
│  │  │  Public APIs │  │  CDP Browser     │  │  Voyager API │  │  (Local)             │        │  │  │
│  │  │  ─────────── │  │  ─────────────── │  │  ─────────── │  │  ────────────────    │        │  │  │
│  │  │  • Guest API │  │  • Real Chrome  │  │  • Pure HTTP │  │  • python-docx      │        │  │  │
│  │  │  • JobSpy    │  │  • Lazy load    │  │  • Session   │  │  • PyMuPDF          │        │  │  │
│  │  │  • JSON-LD   │  │  • Auto-unload  │  │  • OFF by    │  │  • LLM extraction   │        │  │  │
│  │  │  • httpx     │  │  • Human behav  │  │    default   │  │  • Skill matching   │        │  │  │
│  │  │  • Beautiful │  │  • playwright   │  │  • Rate lim  │  └──────────────────────┘        │  │  │
│  │  │    Soup      │  │  • Patchright   │  │     (20/d)   │                                 │  │  │
│  │  │  • Cache     │  │    (fallback)   │  └──────────────┘                                 │  │  │
│  │  └──────┬───────┘  └────────┬─────────┘                                                  │  │  │
│  │         │                   │                                                             │  │  │
│  │         ▼                   ▼                                                             │  │  │
│  │  ┌──────────────┐  ┌──────────────────┐                                                   │  │  │
│  │  │ LinkedIn      │  │ User's REAL      │                                                   │  │  │
│  │  │ Guest Servers │  │ Chrome Browser   │                                                   │  │  │
│  │  │ (no auth)     │  │ (localhost:9222) │                                                   │  │  │
│  │  └──────────────┘  └──────────────────┘                                                   │  │  │
│  │                                                                                              │  │
│  │  SHARED SERVICES:  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │  │  │
│  │                    │ Cache    │ │ Pacing   │ │ Logging  │ │ Storage  │ │ LLM      │        │  │  │
│  │                    │ (TTL)    │ │ Limiter  │ │ structlog│ │ SQLite   │ │ Provider │        │  │  │
│  │                    └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │  │  │
│  └──────────────────────────────────────────────────────────────────────────────────────────────┘  │  │
│                                                                                                    │
└────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Engine Comparison

```yaml
engine_1_public_apis:
  name: "Public APIs"
  icon: "🟢"
  risk: "ZERO"
  requires_account: false
  ram: "25-45 MB"
  tools:
    - search_jobs, get_job, search_multi, get_company_jobs
    - search_companies, get_company, get_job_salary
    - get_job_trends, get_insights, search_jobs_adv
  
  data_sources:
    - "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    - "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    - JobSpy (LinkedIn, Indeed, Google, ZipRecruiter, Glassdoor)
    - JSON-LD Schema.org parsing
  
  rate_limits:
    per_second: 1
    per_minute: 30
    per_hour: 1000
    per_day: 10000
  
  caching:
    ttl: 300  # 5 minutes
    max_entries: 200

engine_2_browser:
  name: "CDP Browser (Your Real Chrome)"
  icon: "🟢"
  risk: "MINIMAL"
  requires_account: true
  ram: "~320 MB (active) / ~25 MB (idle → unloads after 5min)"
  tools:
    - get_profile, get_person, search_people
    - get_inbox, get_convo, get_feed
    - get_notifs, get_sidebar, get_connections
    - get_employees, check_session
  
  connection:
    primary: "CDP via playwright (user's real Chrome)"
    fallback: "Patchright (anti-detection Playwright fork)"
  
  auto_unload:
    idle_timeout: 300  # 5 minutes
    force_unload_timeout: 900  # 15 minutes
  
  humanization:
    delays: "3-15s random (normal distribution)"
    scroll: "jagged patterns"
    mouse: "Bézier curves with jitter"
  
  daily_limits:
    profile_views: 300
    searches: 100
    message_reads: 50
    feed_views: 30

engine_3_voyager:
  name: "Voyager API (Lightweight HTTP)"
  icon: "🟡"
  risk: "LOW (when used sparingly)"
  requires_account: true
  ram: "~27 MB"
  tools:
    - get_profile_voyager (only tool)
  
  disabled_by_default: true
  activation: "--enable-voyager CLI flag"
  
  risk_warning: |
    ⚠️ Voyager API is LinkedIn's internal REST API.
    Using it violates LinkedIn's Terms of Service.
    Accounts detected using Voyager are banned within 3-7 days.
    Only enable if you understand and accept this risk.
  
  rate_limits:
    per_day: 20
    per_hour: 5
  
  auto_disable:
    on_401: true
    duration: 86400  # 24 hours
```

---

## 7. COMPLETE TOOL INVENTORY WITH RISK LABELS

### 7.1 Quick Reference Table

| # | Tool Name | Short Name | Engine | Risk | Est. Tokens | Description |
|---|-----------|-----------|--------|------|-------------|-------------|
| 1 | `search_jobs` | sj | E1 | 🟢 Zero | 500 | Search LinkedIn jobs by keyword/location |
| 2 | `search_jobs_multi` | sjm | E1 | 🟢 Zero | 800 | Search ALL 5 job boards at once |
| 3 | `get_job_details` | gj | E1 | 🟢 Zero | 400 | Full job details + salary from URL |
| 4 | `get_company_jobs` | gcj | E1 | 🟢 Zero | 400 | All open jobs at a company |
| 5 | `get_company_profile` | gcp | E1 | 🟢 Zero | 300 | Company info (size, industry, website) |
| 6 | `search_companies` | sc | E1 | 🟢 Zero | 300 | Search companies by keyword |
| 7 | `get_job_salary` | gjs | E1 | 🟢 Zero | 250 | Extract salary from job posting |
| 8 | `get_job_trends` | gjt | E1 | 🟢 Zero | 400 | Hiring trends by role/location |
| 9 | `get_industry_insights` | gii | E1 | 🟢 Zero | 500 | Market insights for an industry |
| 10 | `search_jobs_advanced` | sja | E1 | 🟢 Zero | 500 | Advanced search with all filters |
| 11 | `analyze_resume` | ar | RE | 🟢 Zero | 400 | Parse resume PDF/DOCX → structured data |
| 12 | `get_resume_insights` | gri | RE | 🟢 Zero | 300 | Skill gaps & improvement suggestions |
| 13 | `match_jobs_to_resume` | mjr | ME | 🟢 Zero | 1500 | Ranked job matches (batched LLM) |
| 14 | `compare_jobs` | cj | ME | 🟢 Zero | 600 | Side-by-side job comparison |
| 15 | `export_jobs` | ej | LO | 🟢 Zero | 100 | Export to CSV/JSON/Excel |
| 16 | `save_job_alert` | sja | ST | 🟢 Zero | 100 | Save recurring job search |
| 17 | `get_saved_alerts` | gsa | ST | 🟢 Zero | 100 | List saved alerts |
| 18 | `check_saved_alerts` | csa | E1+ST | 🟢 Zero | 500 | Run all alerts for new matches |
| 19 | `get_my_profile` | gmp | E2 | 🟢 Minimal | 700 | Your LinkedIn profile (browser) |
| 20 | `get_person_profile` | gpp | E2 | 🟢 Minimal | 700 | View any person's profile |
| 21 | `search_people` | sp | E2 | 🟢 Minimal | 600 | People search by keyword/company |
| 22 | `get_my_connections` | gmc | E2 | 🟢 Minimal | 400 | Your connection list |
| 23 | `get_inbox` | gi | E2 | 🟢 Minimal | 400 | Recent conversations |
| 24 | `get_conversation` | gco | E2 | 🟢 Minimal | 500 | Read a conversation thread |
| 25 | `get_feed` | gf | E2 | 🟢 Minimal | 600 | Your home feed posts |
| 26 | `get_notifications` | gn | E2 | 🟢 Minimal | 300 | Your notifications |
| 27 | `get_sidebar_profiles` | gsp | E2 | 🟢 Minimal | 400 | "People you may know" |
| 28 | `get_company_employees` | gce | E2 | 🟡 Low | 600 | Employees at a company |
| 29 | `check_session` | cs | E2 | 🟢 Minimal | 200 | Check LinkedIn session status |
| 30 | `get_engine_status` | ges | — | 🟢 Zero | 200 | Show available engines |
| 31 | `get_help` | gh | — | 🟢 Zero | 300 | Tool documentation |
| 32 | `get_profile_voyager` | gpv | E3 | 🟡 Low | 300 | Lightweight profile (OFF) |

**Legend:**
- E1 = Engine 1 (Public APIs) | E2 = Engine 2 (CDP Browser) | E3 = Engine 3 (Voyager)
- RE = Resume Engine | ME = Matching Engine | LO = Local Output | ST = Storage
- Token estimates are for TYPICAL output (10 results for search, 1 profile for view)

### 7.2 Detailed Tool Definitions

```python
# Each tool definition is a dataclass — auto-generates MCP schema
@dataclass
class ToolDef:
    """Defines a tool for the MCP server."""
    name: str           # Short name (max 20 chars)
    description: str    # One-line description (max 100 chars)
    engine: str         # "engine1", "engine2", "engine3", "resume", "matching", "storage"
    risk: str           # "zero", "minimal", "low"
    category: str       # "jobs", "companies", "profiles", "messaging", "resume", "matching", "system"
    requires_browser: bool = False
    requires_llm: bool = False
    requires_voyager: bool = False
    tokens_estimate: int = 500  # Average tokens per call
```

```yaml
# ─────────────────────────────────────────────────
# ENGINE 1 TOOLS: ZERO RISK (30 total tools)
# ─────────────────────────────────────────────────

tool_search_jobs:
  name: "search_jobs"
  params:
    kw: "str — Keywords (e.g. 'Python developer')"
    loc: "str — Location (e.g. 'remote', 'San Francisco')"  
    type: "str? — fulltime|parttime|contract|internship"
    exp: "int? — 2=Entry 3=Associate 4=Mid 5=Director 6=Exec"
    remote: "bool? — Filter remote jobs"
    age: "str? — r86400=24h r604800=week r2592000=month"
    limit: "int? — Max results (default 10, max 50)"
  returns: |
    [
      {
        "t":"Sr Python Developer",    # title (compressed)
        "co":"Google",                 # company
        "loc":"Mountain View, CA",     # location
        "sal":"$150-200K/yr",          # salary
        "url":"https://lnkd.in/j/123", # apply URL
        "age":"2d",                    # days since posted
        "type":"FT",                   # employment type
        "desc":"We're looking for...", # truncated description (200 chars)
      }
    ]
  source: |
    GET https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
    Parse: BeautifulSoup + JSON-LD Schema.org
  note: "Zero risk — no LinkedIn account needed"

tool_search_jobs_multi:
  name: "search_jobs_multi"
  params:
    kw: "str — Keywords"
    loc: "str? — Location"
    limit: "int? — Per board (default 5, max 20)"
    age: "int? — Hours old (default 168=1 week)"
  returns: |
    Combined from LinkedIn + Indeed + Google + ZipRecruiter + Glassdoor
    [
      {"t":"Sr Python Dev","co":"Google","site":"li","sal":"$150K","url":"..."},
      {"t":"Python Dev","co":"Meta","site":"in","sal":"$130K","url":"..."},
      {"t":"Backend Eng","co":"Stripe","site":"go","sal":"$160K","url":"..."},
    ]
  source: "JobSpy library — scrapes 5 boards simultaneously"
  note: "Zero risk — uses public APIs only"

tool_get_job_details:
  name: "get_job_details"
  params:
    id: "str — LinkedIn job ID (from URL path)"
  returns: |
    {
      "t":"Senior Python Developer",
      "co":"Google",
      "loc":"Mountain View, CA",
      "sal":"$150,000 - $200,000/yr",
      "type":"Full-time",
      "level":"Mid-Senior",
      "desc":"We're looking for...",
      "skills":["Python","AWS","Django","Kubernetes"],
      "benefits":["Health","Equity","Remote"],
      "url":"https://www.linkedin.com/jobs/view/123456789",
      "posted":"2026-06-10",
      "applicants":"50+ applicants"
    }
  source: |
    1. GET https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}
    2. Parse JSON-LD <script type="application/ld+json">
    3. Fallback: BeautifulSoup DOM traversal
  note: "Zero risk — public job page"

tool_get_company_jobs:
  name: "get_company_jobs"
  params:
    co: "str — Company name (e.g. 'Google')"
    limit: "int? — Max results (default 25)"
  returns: |
    [{"t":"SWE III","loc":"Zurich","age":"3d","url":"..."}, ...]
  source: "LinkedIn Guest API — company job search"
  note: "Zero risk — no login needed"

tool_get_company_profile:
  name: "get_company_profile"
  params:
    co: "str — Company name"
  returns: |
    {"name":"Google","size":"10,000+","industry":"Internet",
     "desc":"...","website":"google.com","founded":1998,"hq":"Mountain View, CA"}
  source: "LinkedIn Guest API + Google Knowledge Panel"
  note: "Zero risk"

tool_search_companies:
  name: "search_companies"
  params:
    kw: "str — Keywords"
    limit: "int? (default 10)"
  returns: |
    [{"name":"Google","industry":"Internet","size":"10K+","loc":"Mountain View, CA"}, ...]
  source: "LinkedIn Guest API"
  note: "Zero risk"

tool_get_job_salary:
  name: "get_job_salary"
  params:
    id: "str — LinkedIn job ID"
  returns: |
    {"min":150000,"max":200000,"currency":"USD",
     "interval":"yearly","source":"direct"}  # or "estimated" if parsed
  source: "JSON-LD Schema.org parsing — most reliable data on LinkedIn"
  note: "Zero risk — structured data"

tool_get_job_trends:
  name: "get_job_trends"
  params:
    kw: "str — Role keywords"
    loc: "str? — Location"
  returns: |
    {"total_jobs":1247,"growth":"+12% MoM",
     "top_companies":[{"name":"Google","count":89},...],
     "avg_salary":"$145K","common_skills":["Python","SQL","AWS"],
     "remote_pct":34}
  source: "Aggregated analysis from multiple searches"
  note: "Zero risk — computed from public data"

tool_get_industry_insights:
  name: "get_industry_insights"
  params:
    ind: "str — Industry name"
  returns: |
    {"industry":"Software Development",
     "top_roles":[{"title":"SWE","avg_sal":"$150K","openings":5000},...],
     "in_demand_skills":["Python","AWS","Go","React"],
     "growth_rate":"+8% YoY"}
  source: "Aggregated from job board data"
  note: "Zero risk"

tool_search_jobs_advanced:
  name: "search_jobs_advanced"
  params:
    kw: "str — Keywords"
    loc: "str? — Location"
    co: "str? — Company name filter"
    type: "str? — fulltime|parttime|contract"
    exp: "int? — Experience level"
    remote: "bool?"
    age: "str? — Time filter"
    sort: "str? — relevance|date"
    limit: "int? (default 10)"
  returns: "Same format as search_jobs"
  note: "Zero risk"

# ─────────────────────────────────────────────────
# RESUME TOOLS: ZERO RISK (All local processing)
# ─────────────────────────────────────────────────

tool_analyze_resume:
  name: "analyze_resume"
  params:
    path: "str — Path to resume file (.pdf or .docx)"
  returns: |
    {
      "name":"Santhakumar K",
      "email":"san@example.com",
      "phone":"+91-...",
      "loc":"India",
      "skills":["Python","FastMCP","AI","Architecture"],
      "exp":[{"co":"...","title":"...","yr":3,"highlight":["..."]}],
      "edu":[{"deg":"B.Tech","inst":"...","yr":2020}],
      "cert":["AWS Solutions Architect"],
      "total_yr":5,"summary":"..."
    }
  source: "python-docx (for .docx) + PyMuPDF (for .pdf) — 100% LOCAL"
  note: "Zero risk — no network call. File never leaves your machine."

tool_get_resume_insights:
  name: "get_resume_insights"
  params:
    id: "int — Resume ID from analyze_resume"
  returns: |
    {
      "gap_skills":["Kubernetes","System Design"],
      "strengths":["Python Expert","AI/ML Experience"],
      "suggestions":["Add cloud certifications","Quantify achievements"],
      "market_pos":"Strong mid-level profile. Top 20% for Python roles."
    }
  source: "LLM analysis (requires API key)"
  note: "Resume text sent to LLM provider. Set OPENAI_API_KEY or ANTHROPIC_API_KEY"

# ─────────────────────────────────────────────────
# MATCHING TOOLS: ZERO RISK (Batched LLM calls)
# ─────────────────────────────────────────────────

tool_match_jobs_to_resume:
  name: "match_jobs_to_resume"
  params:
    id: "int — Resume ID from analyze_resume"
    kw: "str? — Additional search terms"
    loc: "str? — Location preference"
    min_score: "int? — Minimum match % (default 60)"
    limit: "int? — Max results (default 15)"
  returns: |
    {
      "matches":[
        {"rank":1,"t":"Sr Python Dev","co":"Google","loc":"remote",
         "score":96,"match_skills":["Python ✅","AWS ✅","Django ✅"],
         "miss_skills":["Kubernetes ❌"],
         "why":"Strong Python + cloud experience aligns well",
         "url":"https://lnkd.in/j/123"},
        ...
      ],
      "summary":"Found 12 matches. Best: Google Sr Python Dev @ 96%"
    }
  source: "Batched LLM call — 1 call for up to 20 jobs"
  note: "Token efficient: 1 LLM call for all jobs. Zero risk."

tool_compare_jobs:
  name: "compare_jobs"
  params:
    ids: "list[str] — 2-5 job IDs to compare"
  returns: |
    {"columns":["Company","Title","Salary","Location","Remote","Type","Match"],
     "rows":[
       ["Google","Sr Python Dev","$150K","remote","Yes","FT","96%"],
       ["Stripe","Backend Eng","$160K","SF","Hybrid","FT","85%"],
     ]}
  note: "Zero risk. Table format for easy Claude rendering."

# ─────────────────────────────────────────────────
# ALERTS & EXPORT TOOLS: ZERO RISK
# ─────────────────────────────────────────────────

tool_export_jobs:
  name: "export_jobs"
  params:
    ids: "list[str] — Job IDs to export"
    fmt: "str? — csv|json|xlsx (default csv)"
  returns: "File data (binary for xlsx, text for csv/json)"
  note: "Zero risk. Local file generation."

tool_save_job_alert:
  name: "save_job_alert"
  params:
    name: "str — Alert name"
    kw: "str — Keywords"
    loc: "str? — Location"
    freq: "str? — daily|weekly (default daily)"
  returns: {"id":1,"name":"Python Remote","status":"active"}
  note: "Stored in local SQLite"

tool_get_saved_alerts:
  name: "get_saved_alerts"
  params: {}
  returns: [{"id":1,"name":"Python Remote","kw":"Python developer","loc":"remote","freq":"daily"}]

tool_check_saved_alerts:
  name: "check_saved_alerts"
  params:
    ids: "list[int]? — Specific alert IDs (default all)"
  returns: [{"alert_id":1,"name":"Python Remote","new_matches":5,"jobs":[...]}]
  note: "Zero risk. Runs Engine 1 searches for each alert."

# ─────────────────────────────────────────────────
# ENGINE 2 TOOLS: MINIMAL RISK
# ─────────────────────────────────────────────────

tool_get_my_profile:
  name: "get_my_profile"
  params: {}
  returns: |
    {"name":"Santhakumar K","headline":"Developer","loc":"India",
     "about":"...","exp":[...],"edu":[...],"skills":["Python","AI",...],
     "url":"https://linkedin.com/in/santhakumar"}
  requirements: "Chrome running with --remote-debugging-port=9222, logged into LinkedIn"
  note: "🟢 MINIMAL RISK — uses your REAL Chrome browser"

tool_get_person_profile:
  name: "get_person_profile"
  params:
    uname: "str — LinkedIn username (from profile URL)"
  returns: |
    {"name":"...","headline":"...","loc":"...","about":"...",
     "exp":[...],"edu":[...],"skills":[...]}
  requirements: "Chrome running with CDP enabled"
  note: "🟢 MINIMAL RISK — same as browsing manually"

tool_search_people:
  name: "search_people"
  params:
    kw: "str — Keywords"
    loc: "str? — Location"
    co: "str? — Company filter"
    limit: "int? (default 10)"
  returns: [{"name":"...","headline":"...","loc":"...","url":"...","deg":"2nd"}]

tool_get_my_connections:
  name: "get_my_connections"
  params:
    limit: "int? (default 50)"
  returns: [{"name":"...","headline":"...","co":"...","url":"..."}]

tool_get_inbox:
  name: "get_inbox"
  params:
    limit: "int? (default 10)"
  returns: [{"with":"John Doe","last":"Thanks!","ago":"2h","unread":false}]

tool_get_conversation:
  name: "get_conversation"
  params:
    id: "str — Conversation ID or username"
  returns: [{"from":"John","msg":"Hi there!","at":"2026-06-10T14:30"}]

tool_get_feed:
  name: "get_feed"
  params:
    limit: "int? (default 5)"
  returns: [{"author":"John","headline":"CTO @ Co","content":"...","likes":42,"url":"..."}]

tool_get_notifications:
  name: "get_notifications"
  params:
    limit: "int? (default 10)"
  returns: [{"type":"like","msg":"John liked your post","ago":"5m","read":false}]

tool_get_sidebar_profiles:
  name: "get_sidebar_profiles"
  params: {}
  returns: [{"name":"...","headline":"...","reason":"Based on your profile","url":"..."}]

tool_get_company_employees:
  name: "get_company_employees"
  params:
    co: "str — Company name"
    kw: "str? — Role filter"
    limit: "int? (default 25)"
  returns: [{"name":"...","title":"SWE","loc":"...","url":"..."}]

tool_check_session:
  name: "check_session"
  params: {}
  returns: {"valid":true,"user":"Santhakumar K","since":"2h ago"}

# ─────────────────────────────────────────────────
# ENGINE 3 TOOLS: LOW RISK (OFF BY DEFAULT)
# ─────────────────────────────────────────────────

tool_get_profile_voyager:
  name: "get_profile_voyager"
  params:
    uname: "str — LinkedIn username"
  returns: |
    {"name":"...","headline":"...","loc":"...","summary":"...","exp":[...]}
  disabled: true  # Must be explicitly enabled
  note: |
    🟡 LOW RISK — OFF BY DEFAULT.
    Uses LinkedIn's internal Voyager API.
    LinkedIn bans accounts using Voyager within 3-7 days.
    Enable with: --enable-voyager

# ─────────────────────────────────────────────────
# SYSTEM TOOLS
# ─────────────────────────────────────────────────

tool_get_engine_status:
  name: "get_engine_status"
  params: {}
  returns: |
    {"engines":[
      {"name":"Public APIs","risk":"zero","available":true,"tools":10},
      {"name":"CDP Browser","risk":"minimal","available":true,"tools":11},
      {"name":"Voyager","risk":"low","available":false,"enabled":false},
    ],
    "config":{"chrome":"/usr/bin/chromium","llm":"openai","linkedin":"logged_in"}}

tool_get_help:
  name: "get_help"
  params:
    tool: "str? — Tool name (blank = list all)"
  returns: "Tool documentation including parameters, risk level, and requirements"
```

---

## 8. TOKEN BUDGET PER TOOL

### 8.1 Complete Token Budget Table

```yaml
tool_token_budget:
  # ── ENGINE 1: ZERO RISK ──
  search_jobs:
    min: 300   # 5 results
    typical: 500  # 10 results
    max: 2500  # 50 results
    cache_hit: 5  # Near zero
  
  search_jobs_multi:
    min: 400
    typical: 800  # 5 per board × 5 boards
    max: 4000
  
  get_job_details:
    min: 250
    typical: 400
    max: 800
  
  get_company_jobs:
    min: 300
    typical: 400
    max: 1500
  
  get_company_profile:
    min: 200
    typical: 300
    max: 500
  
  search_companies:
    min: 200
    typical: 300
    max: 1000
  
  get_job_salary:
    min: 150
    typical: 250
    max: 400
  
  get_job_trends:
    min: 300
    typical: 400
    max: 600
  
  get_industry_insights:
    min: 400
    typical: 500
    max: 800
  
  search_jobs_advanced:
    min: 300
    typical: 500
    max: 2500
  
  # ── RESUME & MATCHING ──
  analyze_resume:
    min: 300
    typical: 400
    max: 800
  
  get_resume_insights:
    min: 200
    typical: 300
    max: 600
  
  match_jobs_to_resume:
    min: 800   # 5 jobs
    typical: 1500  # 15 jobs (batched)
    max: 3000  # 30 jobs (batched)
    note: "1 batched LLM call — NOT 1 per job"
  
  compare_jobs:
    min: 400
    typical: 600
    max: 1000
  
  export_jobs:
    min: 50
    typical: 100
    max: 200
  
  save_job_alert:
    min: 80
    typical: 100
    max: 150
  
  get_saved_alerts:
    min: 80
    typical: 100
    max: 200
  
  check_saved_alerts:
    min: 300
    typical: 500
    max: 2000
  
  # ── ENGINE 2: MINIMAL RISK ──
  get_my_profile:
    min: 500
    typical: 700
    max: 1500
  
  get_person_profile:
    min: 500
    typical: 700
    max: 1500
  
  search_people:
    min: 400
    typical: 600
    max: 2000
  
  get_my_connections:
    min: 300
    typical: 400
    max: 1500
  
  get_inbox:
    min: 300
    typical: 400
    max: 1000
  
  get_conversation:
    min: 300
    typical: 500
    max: 2000
  
  get_feed:
    min: 400
    typical: 600
    max: 1500
  
  get_notifications:
    min: 200
    typical: 300
    max: 800
  
  get_sidebar_profiles:
    min: 300
    typical: 400
    max: 800
  
  get_company_employees:
    min: 400
    typical: 600
    max: 2000
  
  check_session:
    min: 100
    typical: 200
    max: 300
  
  # ── SYSTEM ──
  get_engine_status:
    min: 100
    typical: 200
    max: 300
  
  get_help:
    min: 200
    typical: 300
    max: 2000  # If listing all tools
  
  # ── ENGINE 3 (OFF) ──
  get_profile_voyager:
    min: 200
    typical: 300
    max: 600
```

### 8.2 Token Optimization Techniques Implemented

```python
# Technique 1: Compressed Field Names
class CompressedOutput(BaseModel):
    """ALL tool outputs use short field names."""
    t: str       # title (not "job_title")
    co: str      # company (not "company_name")  
    loc: str     # location (not "job_location")
    sal: str     # salary (not "salary_range"), formatted as "$150-200K/yr"
    url: str     # URL shortened to path only
    age: str     # relative time: "2d", "1w", "3mo"
    type: str    # type: "FT", "PT", "CT", "IN"
    desc: str    # @field(max_length=300) — truncated description
    # Result: ~50% fewer tokens vs verbose names

# Technique 2: Automatic Truncation
def truncate(text: str, max_chars: int = 200) -> str:
    """Truncate text at word boundary, add ellipsis."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(' ', 1)[0] + '...'
    # Job descriptions are the biggest token consumers
    # Truncating from 1000 chars to 200 saves ~200 tokens

# Technique 3: Null Field Suppression
def clean_output(data: dict) -> dict:
    """Remove null/empty fields from output."""
    return {k: v for k, v in data.items() 
            if v is not None and v != [] and v != {}}
    # A null salary field takes ~15 tokens in JSON
    # Removing it saves 15 tokens × N fields

# Technique 4: Batch Size Control
DEFAULT_LIMITS = {
    'search_jobs': 10,        # Default 10 results (was 25)
    'search_jobs_multi': 5,   # Default 5 per board (was 10)
    'get_inbox': 10,          # Default 10 conversations (was 20)
    'get_feed': 5,            # Default 5 posts (was 10)
    'match_jobs_to_resume': 15, # Default 15 matches
}
# Smaller defaults = fewer tokens = faster responses

# Technique 5: Cache Integration
cache = TTLCache(maxsize=200, ttl=300)  # 5 minute TTL
# User searching "Python developer" twice in 5 min?
# Second call: 5 tokens vs 500 tokens = 99% savings

# Technique 6: Relative Time Format
def format_time(dt: datetime) -> str:
    """'2d' instead of '2026-06-10T14:30:00Z'."""
    delta = datetime.now() - dt
    if delta.days > 0: return f"{delta.days}d"
    if delta.seconds > 3600: return f"{delta.seconds // 3600}h"
    return f"{delta.seconds // 60}m"
    # "2d" = 1 token vs "2026-06-10T14:30:00Z" = ~8 tokens
```

---

## 9. MODULE STRUCTURE

### 9.1 Complete File Tree

```
linkedin-mcp-zero/
│
├── pyproject.toml                    # Build config: hatchling, deps, entry points
├── README.md                         # Quick start, examples, risk disclosure
├── CLAUDE.md                         # Instructions for AI agent contributors
├── LICENSE                           # Apache 2.0
├── .env.example                      # Template for user config
│
├── src/
│   └── linkedin_mcp_zero/
│       ├── __init__.py               # Version: __version__ = "1.0.0"
│       ├── __main__.py               # Entry: if __name__ == "__main__": run()
│       ├── main.py                   # Server bootstrap, auto-config, run
│       │
│       ├── config/
│       │   ├── __init__.py
│       │   ├── settings.py           # pydantic-settings: env + .env + CLI
│       │   ├── defaults.py           # Pacing rules, limits, timeouts
│       │   └── autodetect.py         # OS, Chrome, Python, CDP detection
│       │
│       ├── server/
│       │   ├── __init__.py
│       │   ├── app.py                # FastMCP app factory
│       │   ├── transport.py          # stdio / HTTP transport selector
│       │   ├── lifecycle.py          # Async startup/shutdown hooks
│       │   └── disclaimer.py         # First-run disclaimer display
│       │
│       ├── tools/
│       │   ├── __init__.py           # auto_discover_tools() — finds all tools
│       │   ├── jobs.py               # search_jobs, get_job, search_multi, etc.
│       │   ├── companies.py          # search_companies, get_company, get_company_jobs
│       │   ├── profiles.py           # get_profile, get_person, search_people
│       │   ├── messaging.py          # get_inbox, get_conversation
│       │   ├── feed.py               # get_feed, get_notifications
│       │   ├── resume.py             # analyze_resume, get_resume_insights
│       │   ├── matching.py           # match_jobs_to_resume, compare_jobs
│       │   ├── alerts.py             # save_job_alert, get_saved, check
│       │   ├── insights.py           # get_job_trends, get_industry_insights
│       │   ├── voyager.py            # get_profile_voyager (OFF by default)
│       │   ├── session.py            # check_session, get_engine_status
│       │   └── export.py             # export_jobs (CSV/JSON/XLSX)
│       │
│       ├── engines/
│       │   ├── __init__.py
│       │   ├── base.py               # AbstractBaseEngine
│       │   ├── public_api.py         # Engine 1: Guest API + JobSpy
│       │   ├── browser.py            # Engine 2: CDB + Patchright
│       │   ├── voyager.py            # Engine 3: Voyager HTTP (OFF)
│       │   └── selector.py           # Route tool calls to correct engine
│       │
│       ├── scraping/
│       │   ├── __init__.py
│       │   ├── guest_api.py          # LinkedIn Guest API HTTP client
│       │   ├── job_detail.py         # Job detail page + JSON-LD parser
│       │   ├── company.py            # Company page parser
│       │   ├── profile.py            # Profile page DOM parser
│       │   ├── jobspy_wrapper.py     # JobSpy multi-board integration
│       │   ├── voyager_client.py     # Voyager API HTTP client
│       │   └── schema.py             # Schema.org JSON-LD extraction
│       │
│       ├── browser/
│       │   ├── __init__.py
│       │   ├── cdp_manager.py        # CDP connection via playwright
│       │   ├── pool.py               # Lazy-load, auto-unload manager
│       │   ├── humanize.py           # Mouse, scroll, delay simulation
│       │   └── detect.py             # Chrome/Brave/Edge detection
│       │
│       ├── resume/
│       │   ├── __init__.py
│       │   ├── parser.py             # python-docx + PyMuPDF parser
│       │   ├── extractor.py          # Skill/experience extraction
│       │   └── models.py             # Resume, Experience, Education models
│       │
│       ├── matching/
│       │   ├── __init__.py
│       │   ├── engine.py             # Orchestrator: search → score → rank
│       │   ├── scorer.py             # Scoring algorithm + LLM prompts
│       │   └── prompts.py            # Prompt templates (batched)
│       │
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── provider.py           # Abstract LLM provider
│       │   ├── openai.py             # OpenAI implementation
│       │   ├── claude.py             # Anthropic implementation
│       │   └── local.py              # Ollama/local implementation
│       │
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── database.py           # SQLite connection manager
│       │   ├── models.py             # Dataclass ↔ SQLite row mapping
│       │   └── migrations.py         # Schema create/upgrade
│       │
│       ├── pacing/
│       │   ├── __init__.py
│       │   ├── limiter.py            # Token bucket rate limiter
│       │   └── rules.py              # Per-tool pacing rules
│       │
│       ├── cache/
│       │   ├── __init__.py
│       │   ├── ttl_cache.py          # TTL + LRU cache
│       │   └── decorators.py         # @cached(ttl=300) decorator
│       │
│       └── utils/
│           ├── __init__.py
│           ├── logging.py            # structlog with PII redaction
│           ├── errors.py             # Error hierarchy → MCP codes
│           ├── retry.py              # Exponential backoff decorator
│           ├── rate_limit.py         # Token bucket algorithm
│           ├── compress.py           # Output compression (field shortening)
│           └── version.py            # Read version from pyproject.toml
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                   # Shared fixtures, mock HTTP server
│   ├── fixtures/                     # Snapshot HTML for testing
│   │   ├── job_search_result.html
│   │   ├── job_detail_page.html
│   │   ├── profile_page.html
│   │   ├── sample_resume.docx
│   │   └── sample_resume.pdf
│   ├── unit/
│   │   ├── test_guest_api.py
│   │   ├── test_job_detail.py
│   │   ├── test_schema.py
│   │   ├── test_resume_parser.py
│   │   ├── test_scorer.py
│   │   ├── test_pacing.py
│   │   ├── test_cache.py
│   │   ├── test_compress.py
│   │   └── test_errors.py
│   ├── integration/
│   │   ├── test_tools_jobs.py
│   │   ├── test_tools_resume.py
│   │   ├── test_engine_selector.py
│   │   └── test_lifecycle.py
│   └── e2e/
│       ├── test_full_pipeline.py
│       └── test_mcp_protocol.py
│
├── docs/
│   ├── ARCHITECTURE.md               # This document
│   ├── API.md                        # Full tool reference
│   ├── SECURITY.md                   # Security model & threat analysis
│   ├── RISK.md                       # Per-tool ban risk assessment
│   └── DEVELOPMENT.md                # How to contribute
│
├── docker/
│   ├── Dockerfile                    # Production image (Engine 1 only)
│   └── docker-compose.yml
│
├── .github/
│   ├── worklows/
│   │   ├── ci.yml                    # Lint + test on PR
│   │   ├── release.yml              # PyPI + Docker on tag
│   │   └── docs.yml                 # Auto-generate docs
│   └── CODEOWNERS
│
└── scripts/
    ├── download_fixtures.py          # Capture live LinkedIn HTML
    ├── generate_docs.py              # API.md from tool definitions
    └── bench.py                      # Performance benchmark
```

---

## 10. DATA FLOW & PROTOCOL

### 10.1 MCP Protocol Flow

```
Client (Claude Desktop)                    Server (linkedin-mcp-zero)
         │                                          │
         │  ┌─────────────────────────────────────┐  │
         │  │  STEP 1: INITIALIZATION             │  │
         │  │  ─────────────────────────          │  │
         │  │  • Client starts server process      │  │
         │  │  • Server auto-configures:           │  │
         │  │    - OS detection                    │  │
         │  │    - Python version check            │  │
         │  │    - Chrome detection                │  │
         │  │    - CDP availability check          │  │
         │  │    - LinkedIn session check          │  │
         │  │    - LLM provider check              │  │
         │  │  • Display disclaimer (first run)    │  │
         │  └─────────────────────────────────────┘  │
         │                                          │
         │  ◄────── JSON-RPC: initialize ────────►  │
         │  ◄────── Server capabilities ──────────  │
         │                                          │
         │  ┌─────────────────────────────────────┐  │
         │  │  STEP 2: TOOL DISCOVERY             │  │
         │  │  ───────────────────────            │  │
         │  │  • Client requests tool list         │  │
         │  │  • Server returns 32 tools with:     │  │
         │  │    - name (short)                    │  │
         │  │    - description (one-line)          │  │
         │  │    - parameters (Pydantic schema)    │  │
         │  │    - risk level (ZERO/MINIMAL/LOW)   │  │
         │  └─────────────────────────────────────┘  │
         │                                          │
         │  ◄────── JSON-RPC: list_tools ─────────► │
         │  ◄────── 32 tool definitions ───────────  │
         │                                          │
         │  ┌─────────────────────────────────────┐  │
         │  │  STEP 3: TOOL EXECUTION              │  │
         │  │  ──────────────────────              │  │
         │  │                                      │  │
         │  │  Example: "Find Python jobs"         │  │
         │  │                                      │  │
         │  │  Client sends:                       │  │
         │  │  {"method":"tools/call",             │  │
         │  │   "params":{"name":"search_jobs",    │  │
         │  │            "arguments":{"kw":"Python │  │
         │  │             developer","loc":"remote │  │
         │  │             ","limit":10}}}          │  │
         │  │                                      │  │
         │  │  Server routes to Engine 1:          │  │
         │  │  1. Check cache → MISS               │  │
         │  │  2. HTTP GET Guest API               │  │
         │  │  3. Parse HTML → JSON-LD             │  │
         │  │  4. Compress output (short fields)   │  │
         │  │  5. Store in cache                   │  │
         │  │  6. Return compressed JSON           │  │
         │  │                                      │  │
         │  │  Server responds:                    │  │
         │  │  {"result":[{"t":"Sr Python Dev",... │  │
         │  │   ...], "meta":{"count":10,          │  │
         │  │   "total":247,"cached":false,        │  │
         │  │   "risk":"zero","engine":"E1",       │  │
         │  │   "tokens":480}}                     │  │
         │  └─────────────────────────────────────┘  │
         │                                          │
         │  ┌─────────────────────────────────────┐  │
         │  │  STEP 4: RESUME PIPELINE (example)   │  │
         │  │  ───────────────────────────         │  │
         │  │                                      │  │
         │  │  Call 1: analyze_resume(path.pdf)    │  │
         │  │  → Local parse (no network)          │  │
         │  │  → LLM extraction (1 call)           │  │
         │  │  → Return structured resume          │  │
         │  │                                      │  │
         │  │  Call 2: match_jobs_to_resume(id=1)  │  │
         │  │  → Engine 1: search all job boards   │  │
         │  │  → Batched LLM: score 20 jobs in 1   │  │
         │  │  → Ranked results with scores        │  │
         │  │                                      │  │
         │  │  Call 3: export_jobs(ids=[1,2,3])    │  │
         │  │  → Generate CSV/JSON/XLSX file       │  │
         │  │  → Return file path or content       │  │
         │  └─────────────────────────────────────┘  │
```

### 10.2 Response Format

```json
{
    "result": [...],      // Compressed tool output
    "meta": {
        "risk": "zero",   // Risk level for transparency
        "engine": "E1",   // Which engine handled it
        "tokens": 480,    // Estimated token count
        "cache": "hit",    // "hit" or "miss"
        "total": 247,     // Total available results
        "returned": 10    // Results returned this call
    }
}
```

---

## 11. RESOURCE USAGE BUDGET

### 11.1 Memory Budget

```yaml
scenario_idle_no_engine_loaded:
  python_interpreter: "~15 MB"
  fastmcp_libraries: "~5 MB"
  httpx_pool: "~2 MB"
  config: "~1 MB"
  cache_empty: "~0.5 MB"
  total: "~23.5 MB"

scenario_engine_1_active_search_jobs:
  + httpx_request: "~2 MB"
  + beautifulsoup_parse: "~5 MB"
  + job_data_buffer: "~2 MB"
  total: "~32.5 MB"

scenario_engine_1_active_jobspy:
  + jobspy_library: "~10 MB"
  + pandas_dataframe: "~5 MB"
  total: "~38.5 MB"

scenario_resume_analysis:
  + pymupdf_pdf_load: "~15 MB"
  + parsed_resume: "~2 MB"
  total: "~40.5 MB"

scenario_llm_matching:
  + llm_response_buffer: "~5 MB"
  + job_data: "~5 MB"
  total: "~33.5 MB"

scenario_engine_2_browser_active:
  + playwright_connection: "~25 MB"
  + chrome_tab: "~250 MB"
  + page_dom: "~20 MB"
  total: "~318.5 MB"
  auto_unload_after: "5 minutes idle → ~23.5 MB"

scenario_engine_2_browser_idle:
  auto_unload: true
  total: "~23.5 MB"
  unload_time: "5 minutes after last action"

scenario_engine_3_voyager:
  total: "~25.5 MB"  # Same as idle + minimal HTTP

scenario_concurrent_everything:
  note: "Engines are mutually exclusive by design"
  reason: "Engine 1 does NOT use browser. Engine 2 can run alongside Engine 1."
  estimate: "~60 MB (Engine 1 + Engine 2 cold)"
```

### 11.2 Storage Budget

```yaml
package_install:
  dependencies: "~25 MB"
  browser_binaries: "~150 MB (chromium) — only if Patchright fallback used"

runtime_data:
  sqlite_database: "~1-5 MB (alerts, resume cache, usage stats)"
  cache_files: "~1 MB"
  config_files: "~0.1 MB"
  
user_profile:
  browser_profile_if_used: "~50 MB"
  total_without_browser: "~2 MB"
  total_with_browser: "~52 MB"
```

### 11.3 CPU Budget

```yaml
idle: "~0% CPU"
search_jobs: "~2% CPU for 0.5s"
search_jobs_multi: "~8% CPU for 2s (5 boards parallel)"
parse_resume: "~10% CPU for 1s (PDF parsing)"
llm_matching: "~5% CPU (mostly waiting for LLM API)"
browser_profile: "~15% CPU for 3s (page render + parse)"
```

---

## 12. ERROR HANDLING & RECOVERY

### 12.1 Error Hierarchy

```
LinkedInMCPError (Base)
├── EngineError
│   ├── EngineNotAvailable   → Engine not configured
│   ├── EngineAuthRequired   → Need to log in
│   └── EngineTimeout        → Request timed out
├── LinkedInAPIError
│   ├── RateLimited          → HTTP 429 → retry with backoff
│   ├── Blocked              → HTTP 403 → wait 1 hour
│   ├── AuthWall             → Redirected to login → use Engine 2
│   └── NotFound             → HTTP 404 → job/company not found
├── ParseError
│   ├── HTMLChanged          → LinkedIn changed page structure
│   └── JSONLDNotFound       → No structured data on page
├── InputError
│   ├── ValidationError      → Invalid parameter values
│   └── FileError            → Resume file not found/unreadable
├── LLMError
│   ├── ProviderNotConfigured→ No API key set
│   ├── ProviderTimeout      → LLM API timeout
│   └── ProviderQuota        → Rate limit or quota exceeded
└── StorageError
    ├── DatabaseError        → SQLite corruption
    └── MigrationError       → Schema version mismatch
```

### 12.2 Recovery Strategies

```python
RECOVERY_STRATEGIES = {
    RateLimited: RetryStrategy(
        max_retries=3,
        backoff=[2, 5, 15],  # seconds
        action="exponential_backoff",
        user_message="⏳ LinkedIn rate limit hit. Waiting {delay}s..."
    ),
    Blocked: RetryStrategy(
        max_retries=1,
        backoff=[3600],  # 1 hour
        action="long_wait",
        user_message="🚫 LinkedIn blocked this request. Waiting 1 hour..."
    ),
    AuthWall: RetryStrategy(
        max_retries=0,
        action="redirect_user",
        user_message="🔒 This data requires LinkedIn login. Use Engine 2 (browser) or log in first."
    ),
    ProviderNotConfigured: RetryStrategy(
        max_retries=0,
        action="show_help",
        user_message="🤖 LLM provider not configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env"
    ),
    HTMLChanged: RetryStrategy(
        max_retries=0,
        action="log_issue",
        user_message="⚠️ LinkedIn changed their page structure. This tool needs an update."
    ),
}
```

---

## 13. PHASED BUILD PLAN

### Phase 1: Foundation + Engine 1 (Days 1-3)

```yaml
goal: "Working server with 10 zero-risk job/company tools"
estimated_ram: "~25 MB"
estimated_tokens_per_call: "~400"
depends_on: []

day_1_project_setup:
  - Initialize pyproject.toml with all dependencies
  - Create directory structure
  - Implement config/settings.py (pydantic-settings)
  - Implement config/defaults.py (constants, pacing)
  - Implement config/autodetect.py (OS, Python, Chrome)
  - Implement utils/logging.py (structlog)
  - Implement utils/errors.py (error hierarchy)
  - Implement utils/compress.py (output compression)
  - Implement utils/rate_limit.py (token bucket)
  - Implement utils/retry.py (exponential backoff)
  
day_2_mcp_server:
  - Implement server/app.py (FastMCP factory)
  - Implement server/transport.py (stdio + HTTP)
  - Implement server/lifecycle.py (startup/shutdown)
  - Implement server/disclaimer.py (first-run notice)
  - Implement engines/base.py (abstract interface)
  - Implement engines/public_api.py (Engine 1)
  - Implement engines/selector.py (tool routing)
  - Implement cache/ttl_cache.py
  - Implement cache/decorators.py
  - Test: MCP protocol initialization

day_3_engine_1_tools:
  - Implement scraping/guest_api.py (Guest API client)
  - Implement scraping/job_detail.py (JSON-LD + BeautifulSoup)
  - Implement scraping/company.py (company search)
  - Implement scraping/schema.py (Schema.org parser)
  - Implement tools/jobs.py (search_jobs, get_job, search_jobs_adv)
  - Implement tools/companies.py (search_companies, get_company, get_company_jobs)
  - Implement pacing/limiter.py
  - Implement pacing/rules.py
  - Test: All tools return correct compressed output
```

### Phase 2: JobSpy + Resume Matching (Days 4-7)

```yaml
goal: "Multi-platform search + full resume matching pipeline"
estimated_ram: "~55 MB"
estimated_tokens_per_call: "~800 (search_multi), ~1500 (match_jobs)"
depends_on: [Phase 1]

day_4_multi_platform:
  - Implement scraping/jobspy_wrapper.py
  - Add search_jobs_multi() to tools/jobs.py
  - Add get_job_salary() to tools/jobs.py
  - Test: Multi-board search returns combined results

day_5_resume_parsing:
  - Implement resume/parser.py (python-docx + PyMuPDF)
  - Implement resume/extractor.py (skill extraction)
  - Implement resume/models.py (Pydantic models)
  - Implement tools/resume.py (analyze_resume)
  - Test: Parse sample .docx and .pdf resumes

day_6_llm_matching:
  - Implement llm/provider.py (abstraction)
  - Implement llm/openai.py
  - Implement llm/claude.py
  - Implement llm/local.py (Ollama)
  - Implement matching/prompts.py (batched prompts)
  - Implement matching/scorer.py (scoring logic)
  - Implement matching/engine.py (orchestrator)
  
day_7_matching_tools:
  - Implement tools/matching.py (match_jobs_to_resume, compare_jobs)
  - Add get_resume_insights() to tools/resume.py
  - Implement tools/insights.py (get_job_trends, get_industry_insights)
  - Implement storage/database.py + models.py
  - Implement tools/alerts.py (save, get, check alerts)
  - Implement tools/export.py (CSV, JSON, XLSX)
  - Test: Full pipeline resume → match → export
```

### Phase 3: Browser Engine + Profile Tools (Days 8-11)

```yaml
goal: "Browser-based profile/messaging/feed tools"
estimated_ram: "~25 MB idle / ~320 MB active (auto-unloads)"
estimated_tokens_per_call: "~700"
depends_on: [Phase 1]

day_8_browser_foundation:
  - Implement browser/detect.py (Chrome detection)
  - Implement browser/cdp_manager.py (CDP connection)
  - Implement browser/pool.py (lazy-load, auto-unload)
  - Implement browser/humanize.py (mouse, scroll, timing)
  
day_9_engine_2:
  - Implement engines/browser.py
  - Implement scraping/profile.py (profile DOM parser)
  - Update engines/selector.py for E2 routing

day_10_profile_tools:
  - Implement tools/profiles.py (get_profile, get_person, search_people)
  - Implement tools/messaging.py (get_inbox, get_conversation)
  - Implement tools/feed.py (get_feed, get_notifications)
  
day_11_browser_completion:
  - Implement tools/session.py (check_session)
  - Add get_sidebar_profiles, get_employees
  - Add get_connections
  - Security audit of CDP implementation
  - Test: All browser tools work correctly
```

### Phase 4: Voyager + Polish + Release (Days 12-15)

```yaml
goal: "Release-ready product with all documentation"
depends_on: [Phase 1, Phase 2, Phase 3]

day_12_voyager:
  - Implement scraping/voyager_client.py
  - Implement engines/voyager.py (OFF by default)
  - Implement tools/voyager.py (get_profile_voyager)
  - Security review of Voyager

day_13_documentation:
  - Write README.md (quick start, examples)
  - Write RISK.md (per-tool ban risk assessment)
  - Write SECURITY.md (threat model)
  - Auto-generate API.md from tool decorators
  - Write DEVELOPMENT.md

day_14_devops:
  - Dockerfile + docker-compose.yml
  - GitHub Actions CI workflow
  - GitHub Actions Release workflow
  - .mcpb bundle script
  - Performance benchmarks

day_15_qa_release:
  - Full E2E test suite
  - Security audit final pass
  - Code freeze (bug fixes only)
  - Release v1.0.0 to PyPI
  - Publish Docker image
  - Create GitHub Release
```

---

## SUMMARY: Why This Architecture Wins

```yaml
overall_assessment:
  ban_risk: "🟢 ZERO for Engine 1 (80% of features), 🟢 MINIMAL for Engine 2 (20% of features)"
  token_efficiency: "~65% fewer tokens vs naive implementation (compressed fields + caching + batching)"
  resource_usage: "~25MB idle — lowest of any LinkedIn MCP server"
  auto_config: "100% automatic — zero manual steps to get started"
  universal_connectivity: "Works with Claude Desktop, Claude Code, Cursor, custom agents — same config"
  open_source_gems: "Combines 10+ best-in-class open-source projects"
  total_tools: "32 tools across 3 engines"
  build_time: "15 days for complete production-ready release"
  maintainability: "Clean module separation, full test coverage, typed interfaces"
```

---

> **Prepared by:** Santhakumar K
> **Role:** Developer & Architect
> **Date:** 2026-06-12
> 
> **Next Step:** Begin Phase 1, Day 1 — Project initialization and core module implementation.
> 
> *"Build it right. Build it safe. Build it token-efficient."*