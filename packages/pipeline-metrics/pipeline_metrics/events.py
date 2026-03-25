"""Pipeline event data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


Stage = Literal["pre-commit", "ci", "ai-review"]
Category = Literal["lint", "type", "security", "test"]
Result = Literal["pass", "fail"]


@dataclass
class PipelineEvent:
    """A single instrumentation event from any stage of the PR pipeline."""

    stage: Stage
    hook_name: str
    category: Category
    result: Result
    affected_files: list[str] = field(default_factory=list)
    pr_number: int | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "hook_name": self.hook_name,
            "category": self.category,
            "result": self.result,
            "affected_files": self.affected_files,
            "pr_number": self.pr_number,
            "timestamp": self.timestamp.isoformat(),
        }
