# Deep Audit — linkedin-mcp-zero (v0.3.4 → v0.3.5)

Full-repo audit performed 2026-07-29: every source file read, all quality gates
executed (`pytest`, `ruff`, `mypy --strict`, `bandit`), runtime bugs reproduced
empirically, and external research cross-checked (MCP stdio transport rules,
LinkedIn `jobs-guest` parameter reference, FastMCP 3.x public APIs).

Severity: 🔴 critical · 🟠 high · 🟡 medium · 🔵 low/polish

---

## 1. Issues found (all reproduced, all fixed in 0.3.5)

### 🔴 Protocol corruption — logs written to stdout
`structlog.configure()` used the default `PrintLoggerFactory` which writes to
**stdout**. Under the stdio transport, stdout is the JSON-RPC channel: every
warning (circuit breaker, failed fetch, LLM fallback…) injected raw log JSON
into the protocol stream — the #1 documented cause of "MCP server just
disconnects". Verified: `log.warning(...)` line appeared on captured stdout.
**Fix:** all logging now resolves and writes to `sys.stderr` at emit time
(dynamic factory, no stale-stream caching), `ConsoleSpanExporter(out=sys.stderr)`,
generated-API-key warning prints to stderr. Verified by spawning the real
server and asserting every stdout line is valid JSON-RPC (`tools/list` = 30).

### 🔴 Docker build was broken
`Dockerfile` copied only `pyproject.toml uv.lock` before `uv sync --frozen
--no-dev`; hatchling requires `README.md` + `src/` at build time →
`OSError: Readme file does not exist` (reproduced). **Fix:** two-stage sync
(`--no-install-project`, then full sync after copying sources), `--no-sync` at
runtime, added `.dockerignore`. Build sequence reproduced successfully.

### 🔴 OpenTelemetry spans were silently dead
`trace_span` checked `_tracer is None` at *decoration* time (import), but
`init_telemetry()` runs later inside `create_app()` — so spans never wrapped,
telemetry never emitted, even with the SDK installed and the env var set.
Reproduced: `wrapped at decoration time: False`. **Fix:** tracer resolved
lazily at call time; verified a span now lands on stderr after init.

### 🟠 "AI" skill false positives everywhere
Substring matching (`skill.lower() in text.lower()`) tagged "AI" on any text
containing `det**ai**l`, `em**ai**l`, `m**ai**nt**ai**n`, `av**ai**lable`.
Reproduced: a plumber job description extracted `['AI']`. Affected
`parse_job_detail`, `analyze_resume`, and `match_jobs_to_resume`.
**Fix:** new `utils/skills.py` — boundary-aware regex matching with
case-sensitivity for ambiguous acronyms (`AI`, `R`) and correct handling of
`C++`, `C#`, `.NET`, `Node.js`; canonical dictionary expanded ~18 → ~80 skills.

### 🟠 Salary filter rejected good jobs
`personalized_job_hunt` parsed `$120,000 - $150,000` with `re.search(r"(\d+)")`
→ **120**, so a $135k job failed a $100k minimum. Reproduced. **Fix:** new
`utils/salary.py` annualizing parser (commas, `K` suffix, `$45/hr` → $93.6k);
jobs with undisclosed salary are kept.

### 🟠 `search_jobs_multi` froze the server
`jobspy.scrape_jobs()` (sync, 5 boards, 30–60s+) ran inline in an async tool,
blocking the entire event loop — every other tool stalled. It also returned
up to `limit * 5` rows. **Fix:** `asyncio.to_thread(...)` + slice to `limit`.

### 🟠 Company filter silently did nothing
`search_jobs_advanced(co=...)` passed the company *name* into `f_C`, which
requires LinkedIn's numeric company id — the filter was silently ignored.
**Fix:** names resolved via the typeahead endpoint (hidden gem #1) with
in-memory cache; honest client-side substring filter as fallback.
`get_company_jobs`/`get_company_profile` now use the resolved `f_C` id too.

### 🟠 Browser tools hijacked the user's active Chrome tab
In CDP mode `_page()` navigated `context.pages[0]` — a tab belonging to the
user's real browser window (their email, banking, whatever was open).
**Fix:** the engine owns a dedicated tab (`_our_page()`), created once and
reused; never touches pre-existing tabs. `get_sidebar_profiles` still
intentionally reads the user's active tab (its documented purpose).

### 🟠 PDF without the `pdf` extra stored garbage as the resume
`extract_resume_text` *returned* the help message as text; `analyze_resume`
then saved a "resume" whose content was `"PDF support requires optional
dependency..."`. Reproduced. **Fix:** raises `ValueError` with clear guidance.

### 🟠 Session checks drained the daily feed budget
`check_session` consumed the 10/day `feed_read` cap — checking readiness ~10
times exhausted the feed tool. **Fix:** dedicated `session_check` bucket (50/day).

### 🟠 API key compared with `!=` (timing side channel)
**Fix:** `secrets.compare_digest`. Also: Bearer/API-key compare paths unified.

### 🟡 Pagination could silently skip jobs
Fixed `range(0, limit, 25)` stepping assumes 25 results/page; community
reports the guest endpoint capping pages at 10 → offsets 10–24 skipped.
**Fix:** advance `start` by rows actually returned (`start += len(parsed)`).

### 🟡 Catalog inconsistencies
`deep_industry_analysis` registered but missing from `TOOLS`; duplicate short
alias `sja` (`search_jobs_advanced` shadowed `save_job_alert` in `get_help`).
Registered-tool count read from private `app.local_provider._components`.
**Fix:** catalog 41 → 42, alias → `sal`, public `await app.list_tools()`,
engine breakdown now sums correctly (9+1+2+3+3+5+7 = 30 default).
**Test:** deduplicated-alias + presence assertions added.

### 🟡 Lifespan set via private attribute
`app._lifespan = handler` (private FastMCP hook). **Fix:**
`FastMCP("linkedin-mcp-zero", lifespan=handler)` public constructor.

### 🟡 OAuth introspection on every request
Each HTTP call paid a full round-trip to the auth server. **Fix:** 60s TTL
introspection cache (bounded).

### 🟡 Metrics DB grew forever
Unbounded `tool_calls` table. **Fix:** pruned to newest
`LINKEDIN_MCP_METRICS_MAX_ROWS` (default 5000) on insert.

### 🟡 Herald of smaller bugs
- `check_saved_alerts` ran sequentially and one failing alert killed the rest
  → concurrent `gather` with per-alert error isolation.
- `export_jobs` overwrote `jobs_export.{fmt}` every call → timestamped names;
  no id cap → 100/call cap; CSV cells starting with `= + - @` are escaped
  (formula injection, fires when opened in Excel/Sheets).
- `match_jobs_to_resume` built the fallback search keyword from an unordered
  `set` (`list(skills)[:3]`) — non-deterministic across processes → `sorted()`.
- `claude mcp list` / `mcp add-json` called without `timeout` → 30s timeouts.
- `--with-extra` used a mutable argparse `default=[]` (append mutates it).
- HTTP middleware: fixed-window rate limiter kept stale-client maps; bounded.
- Hardcoded Anthropic chat model (`claude-3-5-sonnet-20241022`) →
  `LINKEDIN_MCP_LLM_MODEL` (default `claude-sonnet-4-5`).
- `http_proxy/https_proxy` settings existed but were never wired into
  curl_cffi → passed as `proxy=` to the guest session.
- Dead `USER_AGENT` constant in `defaults.py` removed.
- README publish version stale (0.3.2), `.env.example` missing half the
  settings → both updated.
- `test_verify_client_config_ok` required a real `uvx` on PATH → hermetic
  (mocked); 15+ regression tests added in `tests/test_hardening.py`.

---

## 2. Hidden gems discovered (research-backed, implemented)

1. **Typeahead resolution API** — `GET
   https://www.linkedin.com/jobs-guest/api/typeaheadHits?typeaheadType=COMPANY&query=…`
   (and `typeaheadType=GEO&geoTypes=POPULATED_PLACE&origin=jserp` for places)
   resolves human names to the numeric ids that `f_C`/`geoId` actually need.
   This is what makes true company-filtered search possible without login.
2. **`f_AL=true`** — "Easy Apply"-only filter, now exposed as `easy_apply`.
3. **`f_WT` full range** — 1 on-site / 2 remote / 3 hybrid; previously only
   "remote=true" was reachable, now `work="onsite|remote|hybrid"`.
4. **Friendly `f_TPR` aliases** — `24h`/`7d`/`30d` mapped to
   `r86400`/`r604800`/`r2592000`; raw codes still pass through.
5. **`f_TPR` = under-10-applicants filter** exists (`f_JIYN`) but is
   login-dependent — documented, intentionally not used.
6. **Applicant-count extraction** — detail pages carry
   `.num-applicants__caption` ("Over 200 applicants"); now surfaced as `appl`.
7. **FastMCP public APIs** — `FastMCP(lifespan=…)`, `await app.list_tools()`
   replace the private `app._lifespan` / `local_provider._components` usage.
8. **stdio transport rule** (MCP spec + 4 independent sources): anything on
   stdout that isn't JSON-RPC breaks clients — now guarded by a live
   subprocess protocol test and regression tests.

## 3. Deliberately deferred (risk/scope, documented not hidden)

- **Voyager/private API** stays a gated placeholder (account risk) — by design.
- **Patchright fallback** remains opt-in — by design.

### Shipped in v0.3.9 (post-audit follow-ups)

- **`SECURITY.md`** — supported versions, private reporting, full threat
  model; GitHub surfaces it on the Security tab.
- **Live smoke suite** — `tests/test_live_guest_api.py` (`live` marker,
  `LINKEDIN_MCP_LIVE=1`): real search/details/typeahead calls with graceful
  skips on geo-blocks; keeps CI hermetic while enabling real-world validation.
- **Salary provenance passthrough** — `get_job_salary` carries `sal_src`.
- **Proxy consistency** — multi-board fallback now honors HTTP(S)_PROXY too.

### Shipped in v0.3.8 (post-audit follow-ups)

- **`distance` radius param** (research-confirmed upstream filter) on
  `search_jobs_advanced`, clamped at 100 miles.
- **Salary-from-description fallback** — postings without schema-level
  `baseSalary` now still yield `sal` (from ranges/intervals in the text) with
  an explicit `sal_src: schema|desc` provenance marker; context-guarded so
  unrelated money mentions are not misread as pay.
- **Doctor reachability probe** — `--doctor` detects firewall/geo blocks of
  the guest API (verified in this sandbox: correctly reports
  `unreachable:ConnectError`); opt-in (`probe=True`) so
  `get_engine_status` never pays the 3s timeout.

### Shipped in v0.3.7 (post-audit follow-ups)

- **Public health/discovery paths** — `/health` and `/.well-known/*` were
  behind the API-key middleware: load-balancer probes returned 401 and the
  RFC 9728 discovery document was unreachable by unauthenticated clients
  (its entire purpose). Both are now on an explicit allowlist; Docker got a
  matching `curl` HEALTHCHECK.
- **`Retry-After` on 429** — computed from the sliding window's oldest entry.
- **CORS env foot-gun** — `CORS_ALLOWED_ORIGINS=http://a,http://b` crashed
  startup (pydantic-settings JSON-decodes list env vars pre-validation, found
  via regression test); fixed with `NoDecode` + lenient JSON-or-CSV parsing,
  also for `LINKEDIN_MCP_ALLOWED_RESUME_DIRS`.
- CI tests Python 3.13; pre-commit tools unpinned from stale v0.3.0/v1.8.0.

### Shipped in v0.3.6 (previously deferred, now done)

- **`geoId` passthrough** — `search_jobs_advanced(geo=...)` resolves place
  names via the GEO typeahead endpoint (`resolve_geo_id`, cached) or accepts
  numeric geoIds directly; kills location-name ambiguity (Cambridge UK vs MA).
- **XLSX export** — implemented as a dependency-free OOXML writer (stdlib
  `zipfile` + inline-string XML cells; formula-injection immune by
  construction). README's "CSV/JSON/XLSX" claim is now true.
- **`relative_age` future-date clamp** — skewed/stale markup no longer yields
  near-24h nonsense values.

## 4. Verification matrix (final state)

| Gate | Result |
|---|---|
| `pytest` | 138 passed, 3 live-skipped (was 86 + 1 env-dependent failure) |
| `ruff check` / `ruff format --check` | clean / clean |
| `mypy --strict` | 42 source files, no issues |
| `bandit -ll` | no issues |
| Live stdio spawn | 30 tools, stdout 100% JSON-RPC, logs on stderr |
| Tool counts | 30 default / 41 browser / 42 browser+voyager (matches README) |
| Docker build sequence | reproduced successfully |
| Telemetry span emission | verified post-init, exported to stderr |

## v0.3.10 addendum

- **`compact_location` substring mangling** — reproduced: `Indianapolis,
  Indiana` → `"INnapolis, INna"` ("India" replaced inside "Indiana") and
  `New Yorker Hotel` → `"NYer Hotel"` ("New York" replaced inside "New
  Yorker"). The compression now uses word-boundary regex patterns, applied
  longest-phrase-first, and gains 10 more country compressions. "Canada"
  stays un-mapped on purpose: output like `Toronto, CA` would be
  indistinguishable from California listings.
- **Alert `freq` was stored but never honored** — `check_saved_alerts`
  re-scraped every alert on every call whether it was saved as `daily` or
  `weekly`. Scheduled runs now skip alerts inside their frequency window
  (`not_due` + `next_due_in_hours`), explicit `ids` still force a run, and
  failed checks never stamp the timestamp so retries aren't blocked. Unknown
  freq values (hand-edited DB rows) degrade to "daily" rather than
  run-forever, as an anti-hammer. Databases created by older releases get a
  `last_run_at TEXT` column via an automatic `ALTER TABLE` migration.
- **`--version` flag** added to the CLI (was missing entirely).
