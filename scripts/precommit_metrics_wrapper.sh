#!/usr/bin/env bash
# precommit_metrics_wrapper.sh
#
# Wraps `pre-commit run` and emits a PipelineEvent for each hook result.
#
# Usage:
#   ./scripts/precommit_metrics_wrapper.sh [pre-commit args...]
#
# Relies on the pipeline-metrics package being importable in the active
# Python environment (uv run or activated venv).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
METRICS_PKG="${REPO_ROOT}/packages/pipeline-metrics"

# Resolve the Python runner: prefer uv run from the metrics package, fall back
# to whatever python3 is on PATH.
if command -v uv &>/dev/null && [[ -f "${METRICS_PKG}/pyproject.toml" ]]; then
    PYTHON_RUN="uv run --project ${METRICS_PKG} python"
else
    PYTHON_RUN="python3"
fi

# Run pre-commit and capture exit code without letting set -e abort the script.
pre-commit run "$@" 2>&1 | tee /tmp/precommit_output_$$.txt
PRECOMMIT_EXIT="${PIPESTATUS[0]}"

OUTPUT_FILE="/tmp/precommit_output_$$.txt"

# Determine overall result
if [[ "${PRECOMMIT_EXIT}" -eq 0 ]]; then
    OVERALL_RESULT="pass"
else
    OVERALL_RESULT="fail"
fi

# Collect affected files from git (staged files at the time of the run)
AFFECTED_FILES=$(git diff --cached --name-only 2>/dev/null | tr '\n' ',' | sed 's/,$//')

# Emit a single aggregate event for the pre-commit run as a whole.
# Individual hook results can be parsed from OUTPUT_FILE if finer granularity
# is needed in future work.
${PYTHON_RUN} - <<PYEOF
import sys
sys.path.insert(0, "${METRICS_PKG}")
from pipeline_metrics import PipelineMetricsLogger

logger = PipelineMetricsLogger()
files = [f for f in "${AFFECTED_FILES}".split(",") if f]

logger.log_precommit_result(
    hook="pre-commit",
    category="lint",
    result="${OVERALL_RESULT}",
    files=files,
)
print(f"[pipeline-metrics] Logged pre-commit result: ${OVERALL_RESULT} ({len(files)} files affected)")
PYEOF

# Also parse per-hook results from the output when available
${PYTHON_RUN} - <<PYEOF
import re
import sys
sys.path.insert(0, "${METRICS_PKG}")
from pipeline_metrics import PipelineMetricsLogger

logger = PipelineMetricsLogger()
files = [f for f in "${AFFECTED_FILES}".split(",") if f]

# Parse lines like:  "ruff..............................................Passed"
# or                 "bandit............................................Failed"
hook_line = re.compile(r'^([A-Za-z][\w\s\-()]+?)\.*\s+(Passed|Failed|Skipped)\s*$')

with open("${OUTPUT_FILE}") as fh:
    for line in fh:
        m = hook_line.match(line.rstrip())
        if not m:
            continue
        hook_name = m.group(1).strip()
        status_str = m.group(2)
        if status_str == "Skipped":
            continue
        result = "pass" if status_str == "Passed" else "fail"
        logger.log_precommit_result(hook_name, "lint", result, files)

PYEOF

rm -f "${OUTPUT_FILE}"
exit "${PRECOMMIT_EXIT}"
