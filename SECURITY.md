# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 0.3.x (latest) | ✅ |
| < 0.3.0 | ❌ |

## Reporting a Vulnerability

Please **do not** open a public issue for security reports. Use GitHub's
private vulnerability reporting ("Report a vulnerability" on the Security tab)
or contact the maintainer listed in `pyproject.toml`. Include a minimal
reproduction and the affected version. We aim to acknowledge within 72 hours.

## Threat Model (what this server does and does not do)

- **Public no-login tools** scrape LinkedIn's guest (unauthenticated) job
  endpoints using TLS-fingerprint impersonation. No credentials are involved.
  Automated scraping may violate LinkedIn's Terms of Service — use
  responsibly; this project is for educational/research purposes.
- **Local tools** (resume parsing, alerts, exports) read local files only from
  allow-listed directories (path-traversal guarded) and store state in a local
  SQLite data dir. Resume content never leaves the machine unless you enable
  LLM sampling/API providers.
- **Exact token counting** is opt-in and is the *only* mode that sends tool
  response text to a third party (Anthropic's count_tokens API). It requires
  both `ANTHROPIC_API_KEY` and `LINKEDIN_MCP_EXACT_TOKEN_COUNT=true`;
  response payloads are never stored in the metrics DB.
- **HTTP transport** requires an API key (auto-generated and printed to
  *stderr* at startup if unset), constant-time key comparison, per-IP rate
  limiting with `Retry-After`, and optional OAuth 2.1 token introspection
  (60 s cached). `/health` and `/.well-known/*` are intentionally public.
- **Browser mode** is read-only and opt-in; it attaches to your own logged-in
  Chrome via CDP, obeys jittered pacing and per-day action caps, and never
  touches the user's existing tabs (it owns a dedicated tab).
- **Exports** escape spreadsheet formula injection (`= + - @` prefixes in CSV;
  formula elements are never emitted in XLSX).

## Configuration Hygiene

- Never commit `.env`; secrets come from the environment.
- Set a strong `API_KEY` for any non-loopback HTTP deployment.
- Prefer `--transport stdio` (the default) unless you need remote access.
