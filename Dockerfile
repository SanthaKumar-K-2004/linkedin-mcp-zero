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

# Copy dependency manifests only; install deps WITHOUT building the project
# itself (sources are not copied yet and the build needs README.md + src/).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code (README.md is required by hatchling for package metadata)
COPY README.md ./
COPY src/ ./src/

# Now install the project itself into the prepared environment
RUN uv sync --frozen --no-dev

# Expose port for streamable-http mode
EXPOSE 8000

# Run mcp server in streamable-http mode by default
CMD ["uv", "run", "--no-sync", "linkedin-mcp-zero", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
