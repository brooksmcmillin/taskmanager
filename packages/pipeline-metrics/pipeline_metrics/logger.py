"""Pipeline metrics logger — writes structured JSONL events to disk."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .events import Category, PipelineEvent, Result


logger = logging.getLogger(__name__)

DEFAULT_LOG_DIR = Path.home() / ".agents" / "pipeline-metrics"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "events.jsonl"


class PipelineMetricsLogger:
    """Writes structured PipelineEvent records to a JSONL file."""

    def __init__(self, log_file: Path | None = None) -> None:
        self.log_file = log_file or DEFAULT_LOG_FILE
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public logging methods
    # ------------------------------------------------------------------

    def log_precommit_result(
        self,
        hook: str,
        category: Category,
        result: Result,
        files: list[str] | None = None,
    ) -> PipelineEvent:
        """Record the outcome of a single pre-commit hook run."""
        event = PipelineEvent(
            stage="pre-commit",
            hook_name=hook,
            category=category,
            result=result,
            affected_files=files or [],
        )
        self._write(event)
        return event

    def log_ci_result(
        self,
        job: str,
        step: str,
        result: Result,
        pr_number: int | None = None,
    ) -> PipelineEvent:
        """Record the outcome of a CI job step."""
        category = self._infer_category(step)
        event = PipelineEvent(
            stage="ci",
            hook_name=f"{job}/{step}",
            category=category,
            result=result,
            pr_number=pr_number,
            timestamp=datetime.now(timezone.utc),
        )
        self._write(event)
        return event

    def log_ai_review_verdict(
        self,
        section: str,
        verdict: Result,
        pr_number: int | None = None,
    ) -> PipelineEvent:
        """Record the verdict from a single AI review section."""
        category = self._infer_category(section)
        event = PipelineEvent(
            stage="ai-review",
            hook_name=section,
            category=category,
            result=verdict,
            pr_number=pr_number,
            timestamp=datetime.now(timezone.utc),
        )
        self._write(event)
        return event

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write(self, event: PipelineEvent) -> None:
        try:
            with self.log_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event.to_dict()) + "\n")
        except OSError:
            logger.exception("Failed to write pipeline event to %s", self.log_file)

    @staticmethod
    def _infer_category(name: str) -> Category:
        """Best-effort category inference from a hook/step/section name."""
        lower = name.lower()
        if any(k in lower for k in ("lint", "ruff", "eslint", "format", "prettier")):
            return "lint"
        if any(k in lower for k in ("type", "pyright", "mypy", "check")):
            return "type"
        if any(k in lower for k in ("security", "bandit", "secret", "audit")):
            return "security"
        return "test"
