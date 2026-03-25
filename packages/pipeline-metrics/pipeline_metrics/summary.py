"""Pipeline metrics summary — reads JSONL log and computes aggregate stats."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .events import Stage
from .logger import DEFAULT_LOG_FILE


@dataclass
class PipelineMetricsSummary:
    """Aggregate statistics derived from a JSONL pipeline events log."""

    catches_per_stage: dict[str, int] = field(default_factory=dict)
    """Number of failures (catches) per stage."""

    unique_catches_per_stage: dict[str, set[str]] = field(default_factory=dict)
    """Unique hook_names that produced failures per stage."""

    false_positive_rate: float = 0.0
    """Fraction of ai-review failures not corroborated by pre-commit or CI."""

    @classmethod
    def from_log(cls, log_file: Path | None = None) -> "PipelineMetricsSummary":
        """Compute summary statistics from a JSONL events log file."""
        path = log_file or DEFAULT_LOG_FILE
        summary = cls()

        all_stages: list[Stage] = ["pre-commit", "ci", "ai-review"]
        for stage in all_stages:
            summary.catches_per_stage[stage] = 0
            summary.unique_catches_per_stage[stage] = set()

        if not path.exists():
            return summary

        # Collect failures grouped by pr_number + hook_name for corroboration
        ai_fails: list[dict[str, object]] = []
        other_fails: set[tuple[int | None, str]] = set()

        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record: dict[str, object] = json.loads(line)
                except json.JSONDecodeError:
                    continue

                stage = str(record.get("stage", ""))
                result = str(record.get("result", ""))
                hook_name = str(record.get("hook_name", ""))
                pr_number = record.get("pr_number")
                pr_num: int | None = int(pr_number) if pr_number is not None else None  # type: ignore[arg-type]

                if result != "fail":
                    continue

                if stage in summary.catches_per_stage:
                    summary.catches_per_stage[stage] += 1
                    summary.unique_catches_per_stage[stage].add(hook_name)

                if stage == "ai-review":
                    ai_fails.append({"pr_number": pr_num, "hook_name": hook_name})
                elif stage in ("pre-commit", "ci"):
                    other_fails.add((pr_num, hook_name))

        if ai_fails:
            unconfirmed = sum(
                1
                for f in ai_fails
                if (f["pr_number"], f["hook_name"]) not in other_fails
            )
            summary.false_positive_rate = unconfirmed / len(ai_fails)

        return summary
