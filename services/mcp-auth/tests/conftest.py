"""Pytest configuration and fixtures for mcp-auth tests."""

import os

# Set required environment variables before any imports
os.environ.setdefault("TASKMANAGER_CLIENT_ID", "test-client-id")
os.environ.setdefault("TASKMANAGER_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("TASKMANAGER_OAUTH_HOST", "http://localhost:4321")
os.environ.setdefault("MCP_SERVER", "http://localhost:9000")
os.environ.setdefault("MCP_AUTH_SERVER", "http://localhost:9000")
