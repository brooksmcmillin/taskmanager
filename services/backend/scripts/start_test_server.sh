#!/bin/bash
# Start the backend server with test environment configuration

set -e

cd "$(dirname "$0")/.."

# Export environment variables from .env.test
set -a
source .env.test
set +a

# Start uvicorn
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8010
