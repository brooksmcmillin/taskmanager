#!/usr/bin/env bash
# Ensure all Docker runtime commands (CMD/ENTRYPOINT/command:) that use
# "uv run" include --no-sync, preventing uv from trying to sync the
# environment as a non-root user at container startup.

set -euo pipefail

err=0

# Match both shell form (uv run) and JSON array form ("uv", "run")
uv_run_pattern='uv[", ]+run'

for f in $(find . -name Dockerfile); do
  if grep -E "(CMD|ENTRYPOINT).*$uv_run_pattern" "$f" | grep -qv -- '--no-sync'; then
    echo "$f: uv run in CMD/ENTRYPOINT must use --no-sync to avoid permission errors at runtime"
    err=1
  fi
done

if grep -E "command:.*$uv_run_pattern" docker-compose.yml 2>/dev/null | grep -qv -- '--no-sync'; then
  echo "docker-compose.yml: uv run in command must use --no-sync"
  err=1
fi

exit $err
