# Use Python 3.13 slim image
FROM python:3.13-slim

# Set shell options for better error handling
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Set working directory
WORKDIR /app

# Install git (needed for uv sync with git-sourced dependencies)
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Pinned uv version — update intentionally when upgrading uv
COPY --from=ghcr.io/astral-sh/uv:0.6.6 /uv /usr/local/bin/uv

# Copy SDK and framework packages first (needed for local dependencies)
COPY packages/taskmanager-sdk /packages/taskmanager-sdk
COPY packages/mcp-auth-framework /packages/mcp-auth-framework
COPY packages/mcp-resource-framework /packages/mcp-resource-framework

# Copy dependency files
COPY services/mcp-resource/pyproject.toml ./

# Update pyproject.toml to use absolute paths for Docker build, then install dependencies
RUN sed -i 's|path = "../../packages/taskmanager-sdk"|path = "/packages/taskmanager-sdk"|' pyproject.toml \
    && sed -i 's|path = "../../packages/mcp-auth-framework"|path = "/packages/mcp-auth-framework"|' pyproject.toml \
    && sed -i 's|path = "../../packages/mcp-resource-framework"|path = "/packages/mcp-resource-framework"|' pyproject.toml \
    && uv sync --no-dev

# Copy application code
COPY services/mcp-resource/mcp_resource ./mcp_resource

# Create non-root user
RUN adduser --disabled-password --gecos "" appuser
USER appuser

# Expose port
EXPOSE 8001

# Default command
CMD ["uv", "run", "--no-sync", "python", "-m", "mcp_resource.server"]
