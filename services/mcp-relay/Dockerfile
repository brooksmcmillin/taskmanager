# Use Python 3.13 slim image
FROM python:3.13-slim

# Set shell options for better error handling
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Set working directory
WORKDIR /app

# Install uv
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Add uv to PATH
ENV PATH="/root/.local/bin:$PATH"

# Copy dependency files
COPY services/mcp-relay/pyproject.toml ./

# Install dependencies
RUN uv sync --no-dev

# Copy application code
COPY services/mcp-relay/mcp_relay ./mcp_relay

# Move uv to system path and create non-root user
RUN cp /root/.local/bin/uv /usr/local/bin/uv && \
    adduser --disabled-password --gecos "" appuser
USER appuser

# Expose port
EXPOSE 8002

# Default command
CMD ["uv", "run", "--no-sync", "python", "-m", "mcp_relay.server"]
