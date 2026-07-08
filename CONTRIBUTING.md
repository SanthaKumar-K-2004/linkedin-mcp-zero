# Contributing to LinkedIn MCP Zero

## Quick Start
1. Fork and clone
2. `uv sync --extra dev`
3. `uv run pytest` — all tests must pass
4. `uv run ruff check .` — no lint errors
5. `uv run mypy src/` — no type errors

## Adding a New Tool
1. Add the function in `server/app.py` with `@async_tool("engine_name")`
2. Add catalog entry in `server/catalog.py`
3. Add test in `tests/`
4. Update README tool table

## Code Style
- Ruff for formatting and linting (line-length=120)
- structlog for all logging
- Typed functions with return annotations
- `except SpecificError` never bare `except Exception`
