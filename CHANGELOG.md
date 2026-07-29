# Changelog

## [0.3.12] - 2026-07-29
### Fixed
- **Duplicate jobs across paginated search results**: LinkedIn re-ranks
  between page fetches, so the same posting could appear on two pages and
  show up twice in results (also double-weighting trend/insight counts that
  built on them). Pages are now deduped by job id, and a page of pure repeats
  is treated as window exhaustion
- **One malformed card URL no longer kills a whole page of search results**:
  `extract_job_id` raised `ParseError` inside `parse_search_results` for any
  card whose link didn't match the id pattern, discarding up to 25 good rows
  along with the bad one. The card is now kept (id-less) and the parse
  continues

### Added
- **16 behavioral tests for `PublicAPIEngine`** (was the least-covered
  critical path at 24%, now 99%): search/detail caching, company & geo
  resolution wiring, honest unresolvable-company fallback, company-jobs id
  path, typeahead company search + jobs aggregation fallback, profile shape,
  trends/industry aggregation, CLI `--doctor --json` and `--print-config`
- Total coverage 68% → 73%

## [0.3.11] - 2026-07-29
### Added
- **Job criteria mining** (hidden structured data): every LinkedIn job detail
  page embeds a criteria block the JSON-LD schema omits — `get_job_details`
  now exposes it as `cr` with `sen` (seniority level), `func` (job function),
  `ind` (industries), and recovers the employment type from it into `type`
  when the schema lacks `employmentType`

### Fixed
- **Circuit breaker tripped on client errors**: a 404 for an expired job id
  counted as an upstream failure — a handful of bad ids could open the
  breaker and block *every* search for 30 s. Only genuinely upstream-hostile
  statuses (403 / 429 / 5xx) count now
- **Circuit breaker half-open stampede**: the moment the cooldown expired,
  all queued requests rushed through against a still-unhealthy upstream.
  HALF-OPEN now admits exactly one probe; a failed probe reopens the breaker
  immediately with a fresh window
- **Missing employment type leaked the literal string `"NONE"`** in job
  details (`str(None).upper()`) — absent types now stay absent, and
  hyphenated criteria text ("Full-time") compresses like schema values
- **Exact-token counts could be silently dropped**: the fire-and-forget
  anthropic count task was created without a strong reference, so CPython's
  garbage collector could cancel it mid-request; tasks are now retained in a
  set until completion
- **Qdrant vector point ids were unstable and collision-prone**:
  `hash(doc_id)` is process-salted (ids changed every restart) and the
  `digits % 10**8` fallback collapsed distinct ids (`resume_42` vs
  `resume_100000042`) onto the same point, silently overwriting documents.
  Ids are now deterministic `uuid5` strings, and search results expose the
  same `doc_id` key as the fallback backend
- 6 new regression tests (breaker probes, 4xx vs 429 accounting, task
  retention, point-id determinism, criteria parsing, employment-type edge
  cases)

## [0.3.10] - 2026-07-29
### Fixed
- `compact_location` no longer mangles locations with substring replacements:
  "Indianapolis, Indiana" used to come out as "INnapolis, INna" and "New
  Yorker…" as "NYer…" — replacements are now word-boundary-safe regex patterns
  applied longest-first, so abbreviations only fire on real place names
- Saved alerts now actually honor their `daily`/`weekly` frequency: scheduled
  `check_saved_alerts` runs (no explicit ids) skip alerts that were already
  checked inside their window instead of re-scraping LinkedIn every call;
  skipping reports `next_due_in_hours`, and passing explicit ids still forces
  a run. Failed checks do not stamp the window, so retries are never blocked

### Added
- `--version` CLI flag printing `linkedin-mcp-zero <version>`
- SQLite migration adding a `last_run_at` column to `alerts` for existing
  databases (added automatically on startup)
- Broader token-saving location compressions beside the original five:
  Netherlands→NL, Singapore→SG, Australia→AU, Germany→DE, France→FR,
  Spain→ES, Italy→IT, Sweden→SE, Brazil→BR, Japan→JP. "Canada" is
  intentionally never collapsed to "CA" (California already owns that code)
- 5 new regression tests (location boundaries, alert due windows, legacy-db
  migration, freq-aware scheduled runs, `--version`)

## [0.3.9] - 2026-07-29
### Added
- `SECURITY.md` — supported versions, private reporting channel, and a full
  threat model (public scraping, local data, token counting, HTTP transport,
  browser mode, export injection)
- Live integration smoke suite (`tests/test_live_guest_api.py`, marked
  `live`, skipped unless `LINKEDIN_MCP_LIVE=1`): search, job details, and
  company typeahead against the real guest API

### Fixed
- `get_job_salary` now preserves the salary extraction provenance (`sal_src`
  schema/desc) from `get_job_details`
- Multi-board LinkedIn fallback now honors `HTTP_PROXY`/`HTTPS_PROXY` like
  every other guest-API path (it created a bare client before)

## [0.3.8] - 2026-07-29
### Added
- `search_jobs_advanced(distance=...)` — search radius in miles (max 100)
  around `loc`/`geo`, mapped to LinkedIn's `distance` param
- Salary-from-description fallback: when a posting has no schema salary,
  `get_job_details` extracts ranges/intervals from the description text
  ("$120K-$150K", "$120,000 - $150,000 a year", "$45-$55/hr") and marks the
  provenance with `sal_src: schema|desc`; bare figures need nearby salary
  context so "save $5,000" never becomes salary
- `--doctor` now probes guest-API reachability (`LinkedIn guest API: ok` vs
  `unreachable:<ExcType>`) and warns when the network blocks LinkedIn;
  probe is opt-in so `get_engine_status` stays instant

## [0.3.7] - 2026-07-29
### Fixed
- API-key middleware blocked `/health` and `/.well-known/*` behind auth —
  health probes and RFC 9728 discovery are meaningless when authenticated;
  both are now on an explicit public allowlist
- `CORS_ALLOWED_ORIGINS=http://a,http://b` crashed startup (pydantic-settings
  JSON-decodes list env vars before validators); list env vars now accept
  JSON arrays or comma-separated strings via `NoDecode` + a lenient parser
  (applies to `LINKEDIN_MCP_ALLOWED_RESUME_DIRS` too)

### Added
- `429` responses now carry a computed `Retry-After` header
- Docker `HEALTHCHECK` against the (now public) `/health` endpoint
- CI matrix gains Python 3.13; pre-commit pinned to ruff v0.9.6 / mypy v1.15.0
- Regression tests: public-path bypass, introspection cache reuse, env parsing

## [0.3.6] - 2026-07-29
### Added
- `search_jobs_advanced(geo=...)` — place names or numeric geoIds pinned via
  the GEO typeahead endpoint (`typeaheadHits?typeaheadType=GEO`); resolves
  ambiguous location names ("Cambridge", "Portland") deterministically
- `GuestAPIClient.resolve_geo_id` with in-memory cache
- Real XLSX export: pure-stdlib OOXML writer (zip + XML, zero new
  dependencies); inline-string cells are formula-injection immune by design

### Fixed
- `export_jobs(fmt="xlsx")` no longer returns `xlsx_not_enabled`; the README
  promise "CSV/JSON/XLSX" is now true
- `relative_age` on future-dated postings returned near-24h nonsense; clamped
  to "0h"

## [0.3.5] - 2026-07-29
### Security
- Stop writing structlog output to stdout — log lines were corrupting the
  stdio JSON-RPC stream (MCP protocol violation); all logs now go to stderr
- Constant-time API key comparison (`secrets.compare_digest`) in HTTP middleware
- Defuse CSV formula injection in `export_jobs`
- OAuth token introspection results cached for 60s (per-request round-trips removed)
- `subprocess` calls to the Claude CLI now have 30s timeouts (no more hangs)

### Fixed
- Docker build: `uv sync` ran before `README.md`/`src/` were copied — now uses
  `--no-install-project` two-stage sync; added `.dockerignore`; `--no-sync` at runtime
- OpenTelemetry spans were never emitted: `trace_span` resolved the tracer at
  decoration time, before `init_telemetry()` ran; spans now resolve lazily and
  export to stderr
- "AI" skill false-positives: any text containing "det**ai**l"/"em**ai**l" matched;
  skills now use boundary-aware matching (`'AI/ML'`, `C++`, `.NET` still match)
- `personalized_job_hunt` salary filter parsed `$120,000` as **120** and rejected
  good jobs; new annualized parser handles commas, `K` suffixes, and hourly rates
- PDF resume parsing without the `pdf` extra returned the help message *as
  resume text*; it now raises a clear error
- `search_jobs_multi` blocked the whole event loop on synchronous jobspy calls
  (moved to a worker thread) and returned up to 5x the requested limit
- `search_jobs_advanced(co=...)` passed company names to `f_C`, which requires
  numeric ids — names are now resolved via the LinkedIn typeahead API with an
  honest client-side fallback
- Guest search pagination now advances by the number of rows actually returned
  (LinkedIn may cap pages at 10 or 25, fixed offsets silently skipped jobs)
- Browser tools hijacked the user's active Chrome tab via `context.pages[0]`;
  the engine now owns a dedicated tab
- `check_session` drained the 10/day `feed_read` budget; it uses its own
  `session_check` bucket now
- Catalog: added missing `deep_industry_analysis`; fixed duplicate `sja` alias
  (shadowed `save_job_alert` in `get_help`)
- `match_jobs_to_resume` used a non-deterministic set-derived search keyword
- Metrics DB unbounded growth — pruned to `LINKEDIN_MCP_METRICS_MAX_ROWS`
- Exports overwrote `jobs_export.{fmt}` every call; files are now timestamped
- `main --with-extra` used a mutable argparse default
- Generated HTTP API key warning now prints to stderr
- `verify-client` test runs hermetically (no `uvx` binary required)

### Added
- `search_jobs_advanced` gains `work` (onsite/remote/hybrid → `f_WT`) and
  `easy_apply` (`f_AL`) filters; `age` accepts `24h`/`7d`/`30d` aliases
- `search_companies` returns canonical companies with numeric ids via the
  typeahead endpoint (ids work directly in `search_jobs_advanced(co=...)`)
- `get_company_jobs`/`get_company_profile` resolve company names to `f_C` ids
- `get_job_details` extracts applicant counts when present (`appl` field)
- `LINKEDIN_MCP_LLM_MODEL` (configurable Anthropic chat model, was hardcoded)
- Proxy settings (`HTTP_PROXY`/`HTTPS_PROXY`) are now honored by the guest API
- Expanded canonical skill dictionary (~80 skills incl. Go, Rust, Kafka, Spark)
- 15+ regression tests in `tests/test_hardening.py`

## [0.3.4]
### Added
- Semantic job matching with sentence-transformers
- MCP Resources, Prompts, Sampling, and Elicitation
- IBM Docling AI resume parsing
- API key auth + CORS + rate limiting for HTTP transport

### Fixed
- Path traversal vulnerability in resume parsing
- Browser engine race condition
- Duplicate return in get_job_details

### Changed
- Replaced httpx with curl_cffi for TLS impersonation
- Replaced BeautifulSoup with selectolax (10x faster)
- Heavy deps moved to optional extras
