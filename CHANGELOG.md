# Changelog

## [0.4.7] - client integration & clean packaging
### Added
- Native Google Antigravity IDE & agent framework support via `--install-client antigravity`
- Idempotent PyPI release publishing with `skip-existing: true`
- Clean production repository packaging, removing internal audit notes and scratch files
- Dedicated tool integration badges and documentation for Claude, Cursor, VS Code, and Google Antigravity

## [0.4.6] - hardening release
### Fixed (search)
- `co` company filter was sent as LinkedIn `f_C` (needs a numeric id) so company names were ignored; now filtered client-side, numeric ids still use `f_C`
- Duplicate jobs in results (deduped per page and across pages); results now include an ISO `posted` date
- Retries: only 429/5xx are retried, `Retry-After` is honored, 404/403 fail fast and no longer trip the circuit breaker
- Results are re-ranked by title relevance to the query (stable, never drops rows)

### Added (skills)
- `config/skill_taxonomy.py`: aliases (k8s, golang, postgres...), categories and curated relations incl. IT-support/helpdesk/CRM/automation skills
- Fast single-regex extraction, canonical names, guards for ambiguous words (Go, R, C, AI, Spring...)
- `expand_skill_cluster` works on a fresh install (curated + learned, ranked, 2-hop adjacent); `skill_gap()` with transferable-skill credit
- Multi-word skills are no longer split by whitespace when indexing jobs

### Security
- Constant-time API key comparison, brute-force throttling before key check, safe header decoding
- OAuth now fails closed (missing/unverifiable token => 401); OAuth mode no longer also demands the API key
- API key file created with 0600 atomically; secrets hidden from settings repr/logs
- Resume reader blocks hidden paths and files over 10 MB
- **Safe mode (default)**: browser session, `li_at`, Voyager and the stealth Patchright fallback are disabled; set `LINKEDIN_MCP_SAFE_MODE=false` to opt in (account-ban risk)
- Removed User-Agent rotation (evasion + mismatched TLS fingerprint); stable UA
- `fastmcp` pinned `<5` (unpinned install broke with mcp 2.x)

## Earlier changes
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
