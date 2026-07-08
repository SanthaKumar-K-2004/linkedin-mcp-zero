# Changelog

## [Unreleased]
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
