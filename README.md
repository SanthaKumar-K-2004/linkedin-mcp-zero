<div align="center" id="top">

<a href="#top">
  <img src="assets/banner.svg" alt="LinkedIn MCP Zero Banner" width="100%" />
</a>

<br/>
<br/>

[![PyPI Version](https://img.shields.io/pypi/v/linkedin-mcp-zero?style=flat-square&logo=pypi&logoColor=white&color=0A66C2)](https://pypi.org/project/linkedin-mcp-zero/)
[![GitHub Release](https://img.shields.io/github/v/release/SanthaKumar-K-2004/linkedin-mcp-zero?style=flat-square&logo=github&logoColor=white&color=238636)](https://github.com/SanthaKumar-K-2004/linkedin-mcp-zero/releases)
[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastMCP 2.0](https://img.shields.io/badge/FastMCP-2.0%20Native-00F0FF?style=flat-square&logo=fastapi&logoColor=black)](https://modelcontextprotocol.io/)
[![Transports](https://img.shields.io/badge/Transports-Stdio%20%7C%20Streamable--HTTP-8B5CF6?style=flat-square&logo=databricks&logoColor=white)](https://modelcontextprotocol.io/)
[![Tests Passing](https://img.shields.io/badge/Tests-151%20Passed-10B981?style=flat-square&logo=pytest&logoColor=white)](tests/)
[![Security Audit](https://img.shields.io/badge/Security-Bandit%200%20Issues-10B981?style=flat-square&logo=shield&logoColor=white)](https://bandit.readthedocs.io/)
[![Safe Mode](https://img.shields.io/badge/Safe--Mode-Enabled%20(Ban--Proof)-10B981?style=flat-square&logo=security&logoColor=white)](#security)
[![Zero Login](https://img.shields.io/badge/Zero--Login-33%20Default%20Tools-success?style=flat-square&logo=linkedin&logoColor=white)](#tools)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=flat-square)](LICENSE)

<br/>

**A high-performance, public-first Model Context Protocol (MCP) server for real-time LinkedIn talent intelligence, hybrid semantic RAG matching, ghost-job viability scoring, dynamic skill graphs, and privacy-first resume analysis.**

*Zero Login Required (33 Default Public/Local Tools) · 45 Catalog Tools · FastMCP 2.0 Native · Dual Stdio/HTTP Transports*

<br/>

[⚡ Quickstart](#quickstart) •
[🎬 Live Demo](#demo) •
[🛠️ 45 Tools](#tools) •
[🏗️ Architecture](#architecture) •
[📊 Benchmarks](#benchmarks) •
[🚀 Deployment](#deployment) •
[🛡️ Security](#security) •
[❓ FAQ](#faq)

</div>

---

## 🌟 What Sets LinkedIn MCP Zero Apart

<table>
  <tr>
    <td width="50%">
      <h3>🌐 100% Real-Time Authentic Research</h3>
      <p>Direct live interaction with public LinkedIn endpoints via browser TLS impersonation (<code>curl_cffi</code> Chrome 124). <b>Zero mock data, zero synthetic placeholders, and zero stale pre-seeded dumps.</b></p>
    </td>
    <td width="50%">
      <h3>🧠 Dynamic Real-Time Skill Graph</h3>
      <p>Self-learning knowledge graph embedded in SQLite. Automatically tracks and updates technology co-occurrence weights (<code>weight += 1.0</code>) as live postings and candidate profiles are analyzed.</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>⚡ Hybrid RAG &amp; Reciprocal Rank Fusion</h3>
      <p>Combines exact lexical BM25 matching (via SQLite FTS5 with Unicode61 Porter tokenization) with dense semantic vector embeddings fused using <b>Reciprocal Rank Fusion ($k=60$)</b>.</p>
    </td>
    <td width="50%">
      <h3>🛡️ Ghost-Job &amp; Saturation Scoring</h3>
      <p>Proprietary <code>analyze_job_viability</code> engine analyzes posting age, repost frequencies, applicant count velocity, and corporate hiring signals to identify stale or "ghost" job listings.</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>🚀 Dual Transport Architecture</h3>
      <p>Out-of-the-box support for local <b>stdio</b> (Claude Desktop, Cursor, Claude Code, VS Code) and remote <b>streamable-http</b> with OAuth 2.1 authentication and API key protection.</p>
    </td>
    <td width="50%">
      <h3>🔒 Defense-in-Depth Hardening</h3>
      <p>Single-flight request coalescing (prevents thundering herds), cryptographic jitter via <code>secrets</code>, CSV spreadsheet formula injection neutralization, and sliding-window rate limiters.</p>
    </td>
  </tr>
</table>

---

## ⚡ Quickstart & One-Command Setup <a id="quickstart"></a>

### Option A: Automatic Client Configuration (Recommended)

LinkedIn MCP Zero can automatically configure your favorite AI development environment with a single command:

```bash
# 🖥️ Anthropic Claude Desktop (macOS / Windows / Linux)
uvx linkedin-mcp-zero --install-client claude-desktop

# ⚡ Cursor IDE (Project or Global)
uvx linkedin-mcp-zero --install-client cursor

# 💻 Claude Code CLI
uvx linkedin-mcp-zero --install-client claude-code

# 📝 VS Code (Cline / Roo Code / MCP Extension)
uvx linkedin-mcp-zero --install-client vscode

# 🔮 Google Antigravity IDE & Agent Framework
uvx linkedin-mcp-zero --install-client antigravity
```

### Option B: Verify System Health (`--doctor`)

Run the automated diagnostic suite to inspect your Python runtime, SQLite FTS5 support, and live network reachability:

```bash
uvx linkedin-mcp-zero --doctor
```

---

### Option C: Supported AI Tool Integrations & Configurations

Choose your preferred AI client environment below for copy-pasteable JSON configurations and instant setup:

#### 1. Anthropic Claude Desktop
[![Claude Desktop](https://img.shields.io/badge/Claude%20Desktop-D97706?style=for-the-badge&logo=anthropic&logoColor=white)](https://claude.ai/download)

**Configuration File Location:**
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "linkedin-zero": {
      "command": "uvx",
      "args": [
        "linkedin-mcp-zero"
      ]
    }
  }
}
```

---

#### 2. Cursor IDE
[![Cursor](https://img.shields.io/badge/Cursor%20IDE-000000?style=for-the-badge&logo=cursor&logoColor=white)](https://www.cursor.com/)

**Configuration File Location:**
- **Workspace:** `.cursor/mcp.json`
- **Global:** `~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "linkedin-zero": {
      "command": "uvx",
      "args": [
        "linkedin-mcp-zero"
      ]
    }
  }
}
```

---

#### 3. Visual Studio Code (Cline / Roo Code / Continue)
[![VS Code](https://img.shields.io/badge/Visual%20Studio%20Code-007ACC?style=for-the-badge&logo=visualstudiocode&logoColor=white)](https://code.visualstudio.com/)

**Configuration File Location:**
- **macOS:** `~/Library/Application Support/Code/User/mcp.json`
- **Linux:** `~/.config/Code/User/mcp.json`
- **Windows:** `%APPDATA%\Code\User\mcp.json`

```json
{
  "servers": {
    "linkedin-zero": {
      "command": "uvx",
      "args": [
        "linkedin-mcp-zero"
      ]
    }
  }
}
```

---

#### 4. Claude Code CLI
[![Claude Code](https://img.shields.io/badge/Claude%20Code%20CLI-1A1A1A?style=for-the-badge&logo=anthropic&logoColor=white)](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code)

**One-line terminal command:**
```bash
claude mcp add linkedin-zero -- uvx linkedin-mcp-zero
```

---

#### 5. Google Antigravity IDE & Agent Framework
[![Google Antigravity](https://img.shields.io/badge/Google%20Antigravity-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://cloud.google.com/)

**Configuration File Location:**
- **Workspace:** `.agents/mcp_config.json`
- **Global:** `~/.gemini/antigravity-ide/mcp_config.json` or `~/.gemini/config/mcp_config.json`

```json
{
  "mcpServers": {
    "linkedin-zero": {
      "command": "uvx",
      "args": [
        "linkedin-mcp-zero"
      ]
    }
  }
}
```

---

#### 6. Cloud Hosted / Remote Streamable-HTTP
[![Cloud Hosted](https://img.shields.io/badge/Cloud%20Hosted%20(Render%20%7C%20Railway)-8B5CF6?style=for-the-badge&logo=fastapi&logoColor=white)](#deployment)

For remote web apps, distributed teams, or hosted agents connecting over HTTP SSE:

```json
{
  "mcpServers": {
    "linkedin-zero-remote": {
      "url": "https://linkedin-mcp-zero.onrender.com/mcp",
      "headers": {
        "x-api-key": "your-secure-api-token"
      }
    }
  }
}
```

---

## 🎬 Animated Live Execution Demo <a id="demo"></a>

Here is a visual recording of LinkedIn MCP Zero executing a live zero-login query, performing FTS5 Porter BM25 indexing, calculating ghost-job viability, and dynamically updating the SQLite skill co-occurrence graph in real time:

<div align="center">
  <img src="assets/demo.svg" alt="LinkedIn MCP Zero Live Execution Demo" width="100%" />
</div>

<details>
<summary><b>🔍 View Actual Live Terminal Output (Click to Expand)</b></summary>

```text
=== REAL-TIME LINKEDIN INSPECTION ===
Query: "Staff AI Engineer" in "San Francisco, CA"

1. Live Public Network Retrieval:
   [1] ID: 4475151136 | Staff Systems Engineer, Inference @ Anthropic (San Francisco, CA)
   [2] ID: 4483675233 | Research Engineer, Model Optimization @ OpenAI (San Francisco, CA)
   [3] ID: 4301398088 | Principal AI Platform Engineer @ Databricks (San Francisco, CA)

2. Live Job Detail & Dynamic Skill Extraction:
   Title:    Staff Systems Engineer, Inference Infrastructure
   Company:  Anthropic
   Skills:   ['Python', 'PyTorch', 'CUDA', 'Distributed Systems', 'Triton']
   Desc:     "Anthropic is building reliable, interpretable, and steerable AI systems..."

3. SQLite FTS5 BM25 Indexing:
   BM25 Search for "PyTorch": Found Anthropic Staff Systems Engineer (Rank: -0.842)

4. Real-Time Viability & Saturation Analysis:
   Status:          ACTIVE_HIGH_PRIORITY
   Viability Score: 0.98 / 1.0 (0 reposts, posted 4h ago, 28 applicants)

5. Dynamically Learned Graph Connections:
   "PyTorch" dynamically linked to:
      -> cuda (weight: 5.8)
      -> distributed systems (weight: 3.2)
      -> triton (weight: 1.0)
      -> llm serving (weight: 2.1)
```
</details>

---

## 🛠️ Complete Interactive Tool Matrix (45 Tools) <a id="tools"></a>

LinkedIn MCP Zero provides **45 synchronized production tools** organized into distinct risk tiers. 

> **🛡️ Zero-Login Guarantee**: 33 core tools require **zero credentials, zero sessions, and zero browser automation**. Your personal LinkedIn account is never touched and remains 100% protected.

<details open>
<summary><h3>💼 1. Job Discovery &amp; Deep Search (11 Tools — Public / Zero Login)</h3></summary>

| Tool Name | Alias | Risk Tier | Est. Tokens | Description |
|:---|:---:|:---:|:---:|:---|
| [`search_jobs`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L3) | `sj` | 🟢 Public | ~500 | Search public LinkedIn job postings by keyword, location, and filters |
| [`search_jobs_multi`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L13) | `sjm` | 🟢 Public | ~800 | Multi-board meta-search across LinkedIn, Indeed, Glassdoor, RemoteOK, and ZipRecruiter |
| [`get_job_details`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L21) | `gj` | 🟢 Public | ~400 | Fetch complete job description, salary range, metadata, and criteria from URL or ID |
| [`get_company_jobs`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L29) | `gcj` | 🟢 Public | ~400 | Retrieve all active job openings for a specific company identifier |
| [`get_job_salary`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L53) | `gjs` | 🟢 Public | ~250 | Extract structured compensation numbers, currency, and pay periodicity from listings |
| [`get_job_trends`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L61) | `gjt` | 🟢 Public | ~400 | Analyze regional hiring demand, role popularity, and posting volume trends |
| [`get_industry_insights`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L69) | `gii` | 🟢 Public | ~500 | Sector-wide hiring momentum, top hiring companies, and demanded skillsets |
| [`deep_industry_analysis`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L77) | `dia` | 🟢 Public | ~1200 | Deep-dive industry landscape analysis with real-time research and market synthesis |
| [`search_jobs_advanced`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L86) | `sja` | 🟢 Public | ~600 | Filtered search by experience level, remote modality, job type, and posting freshness |
| [`compare_jobs`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L125) | `cj` | 🟢 Public | ~800 | Side-by-side comparative analysis of 2 to 5 job postings across criteria |
| [`personalized_job_hunt`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L317) | `pjh` | 🟢 Public | ~1000 | Interactive career preference matching tailored to target roles and geographies |

</details>

<details>
<summary><h3>🏢 2. Company Signals &amp; Market Research (2 Tools — Public / Zero Login)</h3></summary>

| Tool Name | Alias | Risk Tier | Est. Tokens | Description |
|:---|:---:|:---:|:---:|:---|
| [`get_company_profile`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L37) | `gcp` | 🟢 Public | ~300 | Extract organizational profile, employee counts, headquarters, and industry signals |
| [`search_companies`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L45) | `sc` | 🟢 Public | ~300 | Discover companies matching targeted keywords, industry sectors, and locations |

</details>

<details>
<summary><h3>📄 3. Privacy-First Resume &amp; Career Matching (7 Tools — Local Execution)</h3></summary>

| Tool Name | Alias | Risk Tier | Est. Tokens | Description |
|:---|:---:|:---:|:---:|:---|
| [`analyze_resume`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L94) | `ar` | 🔒 Local | ~600 | Parse local PDF, DOCX, or text resume into structured skills, experience, and education |
| [`get_resume_insights`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L102) | `gri` | 🔒 Local | ~500 | Identify candidate skill gaps, missing keywords, and strategic resume improvements |
| [`tailor_resume`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L106) | `tr` | 🔒 Local | ~800 | Universal multi-role ATS resume tailoring, keyword optimization, and real-time gap analysis |
| [`get_resume_insights_advanced`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L333) | `ria` | 🔒 Local | ~800 | Deep resume critique leveraging client LLM reasoning for high-impact tailoring |
| [`match_jobs_to_resume`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L110) | `mjr` | 🟢 Local/Pub | ~700 | Rank live job postings against candidate resume using Hybrid BM25 + Vector RRF |
| [`smart_match_jobs`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L292) | `smj` | 🟢 Local/Pub | ~900 | AI-driven semantic match reasoning providing qualitative candidate-job fit analysis |
| [`generate_cover_letter`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L301) | `gcl` | 🟢 Local/Pub | ~800 | Generate tailored, high-converting cover letters mapped to actual job requirements |

</details>

<details>
<summary><h3>🧠 4. Dynamic AI, Skill Graph &amp; Viability (4 Tools — Next-Gen Analytics)</h3></summary>

| Tool Name | Alias | Risk Tier | Est. Tokens | Description |
|:---|:---:|:---:|:---:|:---|
| [`analyze_job_viability`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L341) | `ajv` | 🟢 Public | ~350 | **Ghost job detector**: Evaluates repost history, applicant saturation, and hiring probability |
| [`expand_skill_cluster`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L349) | `esc` | 🔒 Local | ~200 | **Dynamic Skill Graph**: Query live technology co-occurrence networks learned in SQLite |
| [`analyze_salary_offer`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L309) | `aso` | 🟢 Local/Pub | ~600 | Benchmark compensation offers against live scraped market distributions |
| [`get_tool_usage_summary`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L268) | `gtus` | 🔒 Local | ~200 | Real-time breakdown of tool invocation counts, error rates, and token consumption |

</details>

<details>
<summary><h3>🔔 5. Alerts, Sanitized Export &amp; System Health (9 Tools — Local Utilities)</h3></summary>

| Tool Name | Alias | Risk Tier | Est. Tokens | Description |
|:---|:---:|:---:|:---:|:---|
| [`save_job_alert`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L137) | `sja` | 🔒 Local | ~150 | Save recurring search criteria with frequency settings |
| [`get_saved_alerts`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L145) | `gsa` | 🔒 Local | ~200 | List all active recurring job alerts |
| [`check_saved_alerts`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L153) | `csa` | 🟢 Public | ~500 | Poll live postings for matches against all saved alert queries |
| [`export_jobs`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L133) | `ej` | 🔒 Local | ~200 | Export scraped listings to CSV, JSON, or XLSX with formula injection protection |
| [`confirm_export`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L325) | `ce` | 🔒 Local | ~100 | Human-in-the-loop user approval for saving exports to filesystem |
| [`get_engine_status`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L244) | `ges` | 🔒 Local | ~150 | Inspect SQLite FTS5 database stats, cache hits, and circuit breaker status |
| [`get_help`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L252) | `gh` | 🔒 Local | ~100 | Interactive parameter documentation and schema inspector for all tools |
| [`get_usage_stats`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L260) | `gus` | 🔒 Local | ~100 | Cumulative session tokens and tool invocation statistics |
| [`reset_usage_stats`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L276) | `rus` | 🔒 Local | ~50 | Reset local telemetry metrics |

</details>

<details>
<summary><h3>🌐 6. Opt-In Authenticated Browser CDP Suite (11 Tools — Account Risk Notice)</h3></summary>

> [!WARNING]
> **⚠️ Account Risk & Platform Policy Disclosure**:
> Unlike the 33 default tools which use public TLS impersonation with **zero credentials and zero account risk**, these 11 browser tools interact directly with an active, logged-in Chrome browser session via Chrome DevTools Protocol (`--remote-debugging-port=9222`) or Patchright.
> - **Platform Risk**: Programmatic scraping of authenticated LinkedIn sessions violates LinkedIn's User Agreement. Over-use or automated scanning may trigger CAPTCHA checkpoints or account restrictions.
> - **Best Practice**: If you choose to enable browser mode with `--enable-browser`, **use a secondary or test account**, keep request rates conservative, and never run bulk automation on your primary personal account.
> - **Stay Zero-Risk**: For job hunting, salary benchmarking, ATS resume tailoring, and talent research, the **33 default public/local tools provide 100% of the capability with zero account risk**.

*Requires Chrome with remote debugging (`google-chrome --remote-debugging-port=9222`) and `--with-extra browser`.*

| Tool Name | Alias | Risk Tier | Est. Tokens | Description |
|:---|:---:|:---:|:---:|:---|
| [`get_my_profile`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L161) | `gmp` | ⚠️ Browser | ~500 | Read personal authenticated profile summary, headline, and experience |
| [`get_person_profile`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L169) | `gpp` | ⚠️ Browser | ~500 | Read public or 1st-degree connection profile page details |
| [`search_people`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L177) | `sp` | ⚠️ Browser | ~600 | People search executed through active authenticated Chrome session |
| [`get_my_connections`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L185) | `gmc` | ⚠️ Browser | ~600 | Read connection roster names, titles, and connection timestamps |
| [`get_inbox`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L193) | `gi` | ⚠️ Browser | ~500 | List recent conversation summaries and unread thread counts |
| [`get_conversation`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L201) | `gco` | ⚠️ Browser | ~600 | Read conversation transcript messages (SSRF domain guarded) |
| [`get_feed`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L210) | `gf` | ⚠️ Browser | ~600 | Read authenticated LinkedIn home feed posts and updates |
| [`get_notifications`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L218) | `gn` | ⚠️ Browser | ~400 | Read incoming network notifications and interaction alerts |
| [`get_sidebar_profiles`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L226) | `gsp` | ⚠️ Browser | ~400 | Extract "People Also Viewed" sidebar profile recommendations |
| [`get_company_employees`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L234) | `gce` | ⚠️ Browser | ~500 | Browse authenticated company employee roster directory |
| [`check_session`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L284) | `cs` | ⚠️ Browser | ~100 | Verify Chrome DevTools Protocol connectivity and login state |

</details>

<details>
<summary><h3>🔒 7. Gated Voyager Engine (1 Tool — Advanced Internal Endpoint)</h3></summary>

| Tool Name | Alias | Risk Tier | Est. Tokens | Description |
|:---|:---:|:---:|:---:|:---|
| [`get_profile_voyager`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/catalog.py#L284) | `gpv` | ⛔ Disabled by Default | ~500 | Query internal LinkedIn Voyager API via `curl_cffi` session (requires explicit `VOYAGER_ENABLED=true` opt-in) |

</details>

---

## 🏗️ System Flow & Hybrid RAG Architecture <a id="architecture"></a>

<div align="center">
  <img src="assets/mcp_flow.jpg" alt="LinkedIn MCP Zero End-to-End System Flow Architecture" width="100%" />
</div>

<br/>

### 1. High-Level System Flow

```mermaid
flowchart TD
    classDef client fill:#1e1e38,stroke:#8B5CF6,stroke-width:2px,color:#fff;
    classDef server fill:#0f172a,stroke:#0A66C2,stroke-width:2px,color:#fff;
    classDef engine fill:#064e3b,stroke:#10B981,stroke-width:2px,color:#fff;
    classDef rag fill:#312e81,stroke:#6366F1,stroke-width:2px,color:#fff;
    classDef ext fill:#18181b,stroke:#71717a,stroke-width:1.5px,color:#fff;

    subgraph ClientLayer["🤖 AI Clients & Orchestrators"]
        C1["Claude Desktop"]:::client
        C2["Cursor IDE"]:::client
        C3["Claude Code CLI"]:::client
        C4["Remote Agent via Streamable-HTTP"]:::client
    end

    subgraph CoreServer["⚡ LinkedIn MCP Zero (FastMCP 2.0 Engine)"]
        direction TB
        
        MW["Security & Rate Limiting Middleware<br/>(RFC 6585 · Single-Flight Coalescer · OAuth 2.1)"]:::server
        Router{"45-Tool Router"}:::server

        subgraph ScrapeEngine["Live Guest Scraping Engine"]
            CF["curl_cffi Chrome 124 TLS Impersonator"]:::engine
            HP["JSON-LD & DOM Extractors"]:::engine
            JIT["Cryptographic Jitter (secrets)"]:::engine
        end

        subgraph RAGEngine["Hybrid Retrieval & Knowledge Engine"]
            FTS["SQLite FTS5 Full-Text Index<br/>(Unicode61 Porter Stemming)"]:::rag
            VEC["Dense Semantic Vector Store<br/>(Cosine Similarity)"]:::rag
            RRF["Reciprocal Rank Fusion (RRF)<br/>Score = 1 / (60 + Rank_BM25) + 1 / (60 + Rank_Vec)"]:::rag
            DSG["Dynamic In-Process Skill Graph<br/>(Real-Time Edge Weight Co-occurrence)"]:::rag
        end

        subgraph Intelligence["Decision & Viability Intelligence"]
            GHOST["Ghost Job & Saturation Detector<br/>(analyze_job_viability)"]:::server
            RESUME["Privacy-First Resume Parser<br/>(PDF / DOCX / Text)"]:::server
            LLM_BRIDGE["LLM Sampling Bridge<br/>(Client-Side or Provider API)"]:::server
        end
    end

    subgraph ExternalWeb["🌍 Production Web"]
        LI["LinkedIn Public Gateway<br/>(Guest Search Endpoints)"]:::ext
        MB["Multi-Board Engines<br/>(Indeed, Glassdoor, RemoteOK)"]:::ext
    end

    ClientLayer <==>|Stdio / Streamable-HTTP| MW
    MW --> Router
    Router --> ScrapeEngine
    Router --> RAGEngine
    Router --> Intelligence

    ScrapeEngine <==>|Direct HTTPS TLS| LI
    ScrapeEngine <==>|Direct HTTPS| MB

    HP --> FTS
    HP --> DSG
    RESUME --> DSG
    FTS & VEC --> RRF
```

---

### 2. End-to-End Execution Sequence

```mermaid
sequenceDiagram
    autonumber
    actor User as AI Client (Claude / Cursor / Agent)
    participant MW as Security Middleware & Coalescer
    participant FastMCP as FastMCP 2.0 Router
    participant Engine as Live Scraping Engine (curl_cffi)
    participant Web as LinkedIn Public Gateway
    participant SQLite as SQLite FTS5 & Skill Graph
    participant RRF as Hybrid RRF Ranker

    User->>MW: Call tool: search_jobs("Staff AI Engineer", "SF")
    MW->>FastMCP: Deduplicated Request Passed (Single-Flight Protected)
    FastMCP->>Engine: Dispatch Scraping Task
    Engine->>Web: TLS Chrome 124 Impersonated GET Request
    Web-->>Engine: 200 OK (Live HTML & JSON-LD Postings)
    Engine->>SQLite: Index Postings into FTS5 & Learn Skill Co-occurrences
    FastMCP->>RRF: Query FTS5 BM25 + Vector Similarity
    RRF-->>FastMCP: Reciprocal Rank Fused Scores (k=60)
    FastMCP-->>User: Structured Clean JSON Payload (<600 tokens)
```

---

### 3. Concrete Architectural Implementation Layers

LinkedIn MCP Zero is structured into **5 decoupled, production-hardened subsystems**:

#### Layer 1: Unified Transport & Gateway
- **Implementation**: [`src/linkedin_mcp_zero/server/app.py`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/app.py) & [`src/linkedin_mcp_zero/server/middleware.py`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/server/middleware.py)
- **FastMCP 2.0 Native**: Supports both local process IPC (`stdio`) for desktop AI clients and asynchronous network daemon (`streamable-http`) for cloud containers.
- **Security Middleware**: Sliding-window rate limiting emitting RFC 6585 `Retry-After: 60` headers, token verification, and OAuth 2.1 metadata endpoint.

#### Layer 2: Zero-Login Scraping & Impersonation Engine
- **Implementation**: [`src/linkedin_mcp_zero/engines/public_api.py`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/engines/public_api.py) & [`src/linkedin_mcp_zero/engines/multi_board.py`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/engines/multi_board.py)
- **Browser-Grade TLS**: Uses `curl_cffi` targeting public LinkedIn guest endpoints (`/jobs-guest/jobs/api/seeMoreJobPostings/search`) with Chrome 124 JA3/JA4 TLS fingerprinting.
- **Single-Flight Coalescing**: Duplicate parallel requests for identical queries share the same in-flight task to eliminate thundering herds and IP rate limits.
- **Anti-Fingerprinting**: Cryptographic randomness via Python `secrets` for headers, User-Agent rotations, and network jitter.

#### Layer 3: Hybrid RAG & Reciprocal Rank Fusion (RRF)
- **Implementation**: [`src/linkedin_mcp_zero/storage/db.py`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/storage/db.py) & [`src/linkedin_mcp_zero/storage/vector_db.py`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/storage/vector_db.py)
- **SQLite FTS5 Full-Text**: Embedded full-text virtual table with Unicode61 Porter tokenization delivering instant BM25 lexical rank.
- **Dense Cosine Vectors**: Lightweight in-process vector store computing semantic embedding similarity.
- **RRF Score Fusion**: Fuses lexical BM25 and dense semantic scores using Reciprocal Rank Fusion ($k=60$):
  $$\text{Score}_{\text{RRF}}(d) = \sum_{m \in \{\text{BM25}, \text{Vector}\}} \frac{1}{60 + \text{Rank}_m(d)}$$

#### Layer 4: Real-Time Dynamic Skill Graph
- **Implementation**: [`src/linkedin_mcp_zero/config/skills.py`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/config/skills.py) & [`src/linkedin_mcp_zero/storage/db.py`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/storage/db.py)
- **Continuous In-Process Learning**: 200+ canonical technical skill nodes. When live postings or candidate resumes are analyzed, co-occurring technologies dynamically update edge weights in SQLite:
  $$\text{Weight}_{A \leftrightarrow B} \leftarrow \text{Weight}_{A \leftrightarrow B} + 1.0$$
- Allows instant query expansion and technology ecosystem exploration via `expand_skill_cluster`.

#### Layer 5: Decision Intelligence & Viability Scoring
- **Implementation**: [`src/linkedin_mcp_zero/engines/matching.py`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/engines/matching.py) & [`src/linkedin_mcp_zero/engines/resume.py`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/engines/resume.py)
- **Ghost-Job Viability Engine** (`analyze_job_viability`): Algorithmic detection evaluating posting age, applicant pool volume, repost frequencies, and hiring velocity.
- **Local In-Memory Resume Parsing**: Extracts structured skills, experience, and education from PDF, DOCX, and TXT with zero cloud data transmission.
- **Model-Agnostic LLM Bridge** ([`src/linkedin_mcp_zero/utils/llm.py`](file:///home/santhakumar/Documents/linkedin-mcp-zero/src/linkedin_mcp_zero/utils/llm.py)): Supports client-side sampling (Claude, Cursor, Gemini) with optional direct OpenAI and Anthropic provider execution.

---

## 📊 Feature Comparison Matrix <a id="benchmarks"></a>

| Feature | stickerdaniel (2.3k★) | Standard Scraping MCPs | **LinkedIn MCP Zero v0.4.7** |
| :--- | :---: | :---: | :---: |
| **Total Synchronized Tools** | ~10 tools | 2–5 tools | **✅ 45 Production Tools** |
| **Zero-Login Public Search** | ❌ None (Requires credentials) | ⚠️ 0–2 tools | **✅ 33 Working Tools (No Login)** |
| **Data Authenticity** | ⚠️ Static/Cached | ❌ Frequent synthetic mocks | **✅ 100% Real-Time Live Network** |
| **Ghost Job & Saturation Analysis** | ❌ None | ❌ None | **✅ Algorithmic (`analyze_job_viability`)** |
| **Dynamic Skill Graph Learning** | ❌ None | ❌ None | **✅ Live SQLite Co-occurrence Learning** |
| **Hybrid BM25 + Vector RRF RAG** | ❌ None | ❌ None | **✅ SQLite FTS5 + Dense Vector RRF ($k=60$)** |
| **Multi-Job Board Federation** | ❌ LinkedIn only | ❌ Single source | **✅ 5 Major Job Boards Integrated** |
| **Local Resume Parsing (PDF/DOCX)** | ❌ None | ❌ None | **✅ Zero-Leakage In-Memory Parsing** |
| **Transport Protocol Support** | Stdio only | Stdio only | **✅ Stdio + Streamable HTTP (FastMCP 2.0)** |
| **Single-Flight Request Coalescing** | ❌ None | ❌ None | **✅ Prevents Duplicate Network Hits** |
| **Spreadsheet Formula Neutralization** | ❌ Unescaped CSV | ❌ Unescaped CSV | **✅ Escapes `=`, `+`, `-`, `@` Formula Injection** |
| **One-Click Diagnostic CLI** | ❌ None | ❌ None | **✅ Built-in `--doctor` Diagnostic** |

---

## 🚀 Production Deployment & Cloud Hosting <a id="deployment"></a>

LinkedIn MCP Zero can be executed locally as a stdio child process or hosted online as a high-performance cloud service via **Streamable HTTP / SSE** mode.

<p align="center">
  <a href="https://render.com/deploy?repo=https://github.com/SanthaKumar-K-2004/linkedin-mcp-zero">
    <img src="https://render.com/images/deploy-to-render-button.svg" alt="Deploy to Render" height="38" />
  </a>
  &nbsp;&nbsp;
  <a href="https://railway.app/template?template=https%3A%2F%2Fgithub.com%2FSanthaKumar-K-2004%2Flinkedin-mcp-zero">
    <img src="https://railway.app/button.svg" alt="Deploy on Railway" height="38" />
  </a>
</p>

### HTTP / Cloud Endpoints
- **Service Status & Discovery**: `GET /` (Public JSON status and tool count)
- **Health & Diagnostic Probe**: `GET /health` (Liveness & readiness probe for cloud balancers)
- **MCP 2.0 Streaming SSE**: `GET /sse` or `POST /sse` (Streamable MCP endpoint for remote AI agents)
- **OAuth 2.1 Discovery**: `GET /.well-known/oauth-protected-resource` (RFC 9728 metadata)

---

### Cloud Provider Quickstart

#### 1. Render (1-Click or Blueprint)
Deploy automatically using [`render.yaml`](file:///home/santhakumar/Documents/linkedin-mcp-zero/render.yaml):
- Click **Deploy to Render** above or connect your GitHub repository in the Render Dashboard.
- Render automatically provisions the Docker container, configures the `/health` check, and sets an auto-generated `LINKEDIN_MCP_API_KEY`.

#### 2. Railway (1-Command CLI)
Deploy using the Railway CLI and [`railway.json`](file:///home/santhakumar/Documents/linkedin-mcp-zero/railway.json):
```bash
npm i -g @railway/cli
railway login
railway init
railway up
```

#### 3. Fly.io (Global Edge Deployment)
Deploy across worldwide regions using [`fly.toml`](file:///home/santhakumar/Documents/linkedin-mcp-zero/fly.toml):
```bash
fly launch --no-deploy
fly secrets set LINKEDIN_MCP_API_KEY="your-secure-key"
fly deploy
```

#### 4. Pre-built Docker Container (GitHub Container Registry)
Run the pre-built, hardened multi-arch image directly:
```bash
docker run -d -p 8000:8000 \
  -e LINKEDIN_MCP_API_KEY="your-secure-token" \
  -e RATE_LIMIT_PER_MINUTE=120 \
  --name linkedin-mcp-zero \
  ghcr.io/santhakumar-k-2004/linkedin-mcp-zero:latest
```

#### 5. Kubernetes Cluster
Deploy to any Kubernetes cluster (GKE, EKS, AKS, or local Minikube/k3s):
```bash
kubectl apply -f deploy/k8s.yaml
```

---

### 🌐 Connecting Remote AI Clients to Hosted Server

Once hosted online (e.g. `https://your-service.onrender.com`), connect your favorite AI client using the remote SSE transport:

#### 🖥️ Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "linkedin-remote": {
      "url": "https://your-service.onrender.com/sse",
      "headers": {
        "x-api-key": "your-secure-token"
      }
    }
  }
}
```

#### ⚡ Cursor IDE (`.cursor/mcp.json`)
```json
{
  "mcpServers": {
    "linkedin-remote": {
      "url": "https://your-service.onrender.com/sse",
      "headers": {
        "x-api-key": "your-secure-token"
      }
    }
  }
}
```

#### 🔮 Google Antigravity IDE (`.agents/mcp_config.json`)
```json
{
  "mcpServers": {
    "linkedin-remote": {
      "url": "https://your-service.onrender.com/sse",
      "headers": {
        "x-api-key": "your-secure-token"
      }
    }
  }
}
```

#### 📝 VS Code
```json
{
  "servers": {
    "linkedin-remote": {
      "url": "https://your-service.onrender.com/sse",
      "headers": {
        "x-api-key": "your-secure-token"
      }
    }
  }
}
```

---

### 🔍 Verification & Health Checking
Verify your remote deployment is live and healthy:
```bash
# Liveness probe
curl -f https://your-service.onrender.com/health

# Discovery endpoint
curl -H "x-api-key: your-secure-token" https://your-service.onrender.com/
```

---

## 🔒 Security & Privacy Model <a id="security"></a>

LinkedIn MCP Zero is architected around **strict defense-in-depth principles**:

1. **Zero-Login by Default**: 33 of 45 tools require **no authentication, no credentials, and no cookies**. Your account cannot be banned or restricted because it is never used.
2. **Privacy-First Local Resume Parsing**: PDF, DOCX, and text resume extraction (`analyze_resume`, `match_jobs_to_resume`) runs completely in local memory on your device using native parsers. Candidate PII, resumes, and contacts are **never sent to external analytics or telemetry services**.
3. **Transparent Client LLM Reasoning**: Qualitative reasoning tools (`tailor_resume`, `smart_match_jobs`, `generate_cover_letter`, `get_resume_insights_advanced`) pass parsed candidate details strictly to your configured AI client (Claude, Cursor, Gemini, or local Ollama) as part of your prompt context. You retain 100% control over the prompt context.
4. **Spreadsheet Formula Injection Neutralization**: All CSV/XLSX export routines prefix any cell starting with `=`, `+`, `-`, `@`, or tab characters with `'` to mitigate CVE-style CSV macro execution.
5. **SSRF Domain Protection**: Internal browser scrapers strictly enforce LinkedIn and recognized multi-board hostname validation to prevent unauthorized network pivot attempts.
6. **Cryptographic Randomness**: All jitter delays, user-agent rotations, and temporary identifiers use Python's cryptographically secure `secrets` module instead of predictable pseudo-random seeds.
7. **Single-Flight Request Coalescing**: Duplicate parallel requests for the same LinkedIn job or company URL are coalesced into a single flight, preventing thundering-herd rate limiting.
8. **RFC 6585 Rate Limiting**: Intelligent sliding-window rate limiters emit standard `Retry-After: 60` headers and thread-safe circuit breakers when upstream rate limits are approached.

---

## 💻 Local Development & Testing

```bash
# Clone repository
git clone https://github.com/SanthaKumar-K-2004/linkedin-mcp-zero.git
cd linkedin-mcp-zero

# Install with development extras
uv sync --extra dev

# Run comprehensive test suite (125 unit tests)
uv run pytest tests/ -v

# Code quality and formatting checks
uv run ruff check .
uv run ruff format --check .

# Strict static type analysis
uv run mypy src/

# Automated security vulnerability scan
uv run bandit -r src/ -x tests -ll

# Build distributable wheel and source packages
uv build
```

---

## ❓ Frequently Asked Questions <a id="faq"></a>

<details>
<summary><b>Do I need a LinkedIn username or password to use this?</b></summary>
<br/>
<b>No!</b> 33 of the 45 tools are 100% public and zero-login. You never supply an email, password, or session cookie. The server accesses public search and job postings using browser-grade TLS fingerprint impersonation.
</details>

<details>
<summary><b>How does the Ghost Job Viability algorithm work?</b></summary>
<br/>
The <code>analyze_job_viability</code> tool evaluates multiple signals: posting creation timestamp vs. repost frequency, applicant velocity over time, job description staleness, and hiring company headcount trajectory. Postings open for over 60 days with multiple repost cycles are flagged as low-viability "ghost jobs".
</details>

<details>
<summary><b>How does the Dynamic Skill Graph learn?</b></summary>
<br/>
Unlike static taxonomy databases that go out of date, LinkedIn MCP Zero tracks skill co-occurrences in real-time. When a job description or resume containing <code>PyTorch</code> and <code>Triton</code> is parsed, the edge weight between those technologies is incremented in the SQLite graph table. The graph becomes smarter with every query!
</details>

<details>
<summary><b>Is my resume or personal data stored externally?</b></summary>
<br/>
<b>Never.</b> All resume parsing (PDF, DOCX, TXT) and skill extraction occur strictly in-memory on your local machine. No candidate data is logged, shared, or sent to any external server.
</details>

<details>
<summary><b>Can I connect this to Claude, Cursor, and custom Python agents simultaneously?</b></summary>
<br/>
<b>Yes.</b> You can run the server locally via stdio for Claude Desktop / Cursor, or run it with <code>--transport streamable-http</code> to serve multiple remote AI agents and web apps over standard HTTP SSE.
</details>

---

## 📄 License & Community

Licensed under the **Apache License, Version 2.0**. See the [LICENSE](LICENSE) file for complete details.

> [!NOTE]
> **Educational & Research Notice**: LinkedIn MCP Zero is developed for research, market analytics, and educational workflow automation. Please adhere to applicable platform terms of service and use responsibly.

<div align="center">
  <sub>Built with ⚡ by the Open Source AI Community · FastMCP 2.0 · Python 3.10+</sub>
</div>
