# Changelog

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
