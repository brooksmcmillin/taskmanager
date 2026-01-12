# Use Python 3.13 slim image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install uv and git
RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Add uv to PATH
ENV PATH="/root/.local/bin:$PATH"

# Copy SDK package first (needed for local dependency)
COPY packages/taskmanager-sdk /packages/taskmanager-sdk

# Copy dependency files
COPY services/mcp-resource/pyproject.toml ./

# Install dependencies using uv
RUN uv sync --no-dev

# Copy application code
COPY services/mcp-resource/mcp_resource ./mcp_resource

# Expose port
EXPOSE 8001

# Default command
CMD ["uv", "run", "python", "-m", "mcp_resource.server"]
