# Use Python 3.13 slim image
FROM python:3.13-slim

# Set shell options for better error handling
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Set working directory
WORKDIR /app

# Install uv and git
RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Add uv to PATH
ENV PATH="/root/.local/bin:$PATH"

# Copy framework package (needed for local dependency)
COPY packages/mcp-resource-framework /packages/mcp-resource-framework

# Copy dependency files
COPY services/mcp-relay/pyproject.toml ./

# Update pyproject.toml to use absolute paths for Docker build, then install dependencies
RUN sed -i 's|path = "../../packages/mcp-resource-framework"|path = "/packages/mcp-resource-framework"|' pyproject.toml \
    && uv sync --no-dev

# Copy application code
COPY services/mcp-relay/mcp_relay ./mcp_relay

# Move uv to system path and create non-root user
RUN cp /root/.local/bin/uv /usr/local/bin/uv && \
    adduser --disabled-password --gecos "" appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8002

# Default command
CMD ["uv", "run", "--no-sync", "python", "-m", "mcp_relay.server"]
