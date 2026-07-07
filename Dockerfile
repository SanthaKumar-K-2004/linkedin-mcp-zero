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

# Copy configuration and lock files
COPY pyproject.toml uv.lock ./

# Install project dependencies (excluding developer extras)
RUN uv sync --frozen --no-dev

# Copy source code and tests
COPY src/ ./src/
COPY README.md ./

# Re-install the package to ensure entry points are registered
RUN uv pip install -e .

# Expose port for streamable-http mode
EXPOSE 8000

# Run mcp server in streamable-http mode by default
CMD ["uv", "run", "linkedin-mcp-zero", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
