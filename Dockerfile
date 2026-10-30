# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Install system dependencies and curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy configuration and project metadata (README required by hatchling)
COPY pyproject.toml uv.lock README.md ./

# Install project dependencies (excluding developer extras)
RUN uv sync --frozen --no-dev

# Copy source code and assets
COPY src/ ./src/
COPY assets/ ./assets/

# Re-install the package to ensure entry points are registered
RUN uv pip install -e .

# Create non-root user for container security
RUN addgroup --system --gid 1001 mcp && \
    adduser --system --uid 1001 --ingroup mcp mcp && \
    chown -R mcp:mcp /app

USER mcp

# Expose port for streamable-http mode
EXPOSE 8000

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run mcp server in streamable-http mode by default
CMD ["uv", "run", "linkedin-mcp-zero", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
