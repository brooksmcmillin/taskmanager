"""Unit tests for PipelineEvent, PipelineMetricsLogger, and PipelineMetricsSummary."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from pipeline_metrics import PipelineEvent, PipelineMetricsLogger, PipelineMetricsSummary


# ---------------------------------------------------------------------------
# PipelineEvent
# ---------------------------------------------------------------------------


class TestPipelineEvent:
    def test_minimal_creation(self) -> None:
        event = PipelineEvent(
            stage="pre-commit",
            hook_name="ruff",
            category="lint",
            result="pass",
        )
        assert event.stage == "pre-commit"
        assert event.hook_name == "ruff"
        assert event.category == "lint"
        assert event.result == "pass"
        assert event.affected_files == []
        assert event.pr_number is None
        assert isinstance(event.timestamp, datetime)

    def test_with_all_fields(self) -> None:
        ts = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)
        event = PipelineEvent(
            stage="ci",
            hook_name="backend/pytest",
            category="test",
            result="fail",
            affected_files=["app/main.py", "tests/test_main.py"],
            pr_number=42,
            timestamp=ts,
        )
        assert event.pr_number == 42
        assert len(event.affected_files) == 2
        assert event.timestamp == ts

    def test_to_dict_structure(self) -> None:
        event = PipelineEvent(
            stage="ai-review",
            hook_name="security-review",
            category="security",
            result="fail",
            pr_number=7,
        )
        d = event.to_dict()
        assert d["stage"] == "ai-review"
        assert d["hook_name"] == "security-review"
        assert d["category"] == "security"
        assert d["result"] == "fail"
        assert d["pr_number"] == 7
        assert isinstance(d["timestamp"], str)
        # Timestamp must be parseable ISO 8601
        datetime.fromisoformat(str(d["timestamp"]))

    def test_to_dict_affected_files(self) -> None:
        event = PipelineEvent(
            stage="pre-commit",
            hook_name="bandit",
            category="security",
            result="fail",
            affected_files=["app/auth.py"],
        )
        d = event.to_dict()
        assert d["affected_files"] == ["app/auth.py"]

    def test_default_timestamp_is_utc(self) -> None:
        event = PipelineEvent(
            stage="pre-commit", hook_name="ruff", category="lint", result="pass"
        )
        assert event.timestamp.tzinfo is not None


# ---------------------------------------------------------------------------
# PipelineMetricsLogger
# ---------------------------------------------------------------------------


class TestPipelineMetricsLogger:
    def test_log_precommit_result_writes_jsonl(self, tmp_path: Path) -> None:
        log_file = tmp_path / "events.jsonl"
        logger = PipelineMetricsLogger(log_file=log_file)
        event = logger.log_precommit_result("ruff", "lint", "fail", ["app/main.py"])

        assert log_file.exists()
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["stage"] == "pre-commit"
        assert record["hook_name"] == "ruff"
        assert record["category"] == "lint"
        assert record["result"] == "fail"
        assert record["affected_files"] == ["app/main.py"]
        assert event.stage == "pre-commit"

    def test_log_ci_result_writes_jsonl(self, tmp_path: Path) -> None:
        log_file = tmp_path / "events.jsonl"
        logger = PipelineMetricsLogger(log_file=log_file)
        logger.log_ci_result("backend", "pytest", "pass", pr_number=12)

        record = json.loads(log_file.read_text().strip())
        assert record["stage"] == "ci"
        assert record["hook_name"] == "backend/pytest"
        assert record["pr_number"] == 12
        assert record["result"] == "pass"

    def test_log_ai_review_verdict_writes_jsonl(self, tmp_path: Path) -> None:
        log_file = tmp_path / "events.jsonl"
        logger = PipelineMetricsLogger(log_file=log_file)
        logger.log_ai_review_verdict("security-review", "fail", pr_number=5)

        record = json.loads(log_file.read_text().strip())
        assert record["stage"] == "ai-review"
        assert record["hook_name"] == "security-review"
        assert record["result"] == "fail"
        assert record["pr_number"] == 5

    def test_multiple_events_append(self, tmp_path: Path) -> None:
        log_file = tmp_path / "events.jsonl"
        logger = PipelineMetricsLogger(log_file=log_file)
        logger.log_precommit_result("ruff", "lint", "pass")
        logger.log_precommit_result("bandit", "security", "fail")

        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        log_file = tmp_path / "deeply" / "nested" / "events.jsonl"
        logger = PipelineMetricsLogger(log_file=log_file)
        logger.log_precommit_result("ruff", "lint", "pass")
        assert log_file.exists()

    def test_os_error_does_not_raise(self, tmp_path: Path) -> None:
        log_file = tmp_path / "events.jsonl"
        logger = PipelineMetricsLogger(log_file=log_file)
        with patch.object(Path, "open", side_effect=OSError("disk full")):
            # Should log the error but not propagate
            logger.log_precommit_result("ruff", "lint", "fail")

    def test_infer_category_lint(self, tmp_path: Path) -> None:
        logger = PipelineMetricsLogger(log_file=tmp_path / "e.jsonl")
        for name in ("ruff-check", "eslint", "prettier", "npm-format"):
            assert logger._infer_category(name) == "lint"

    def test_infer_category_type(self, tmp_path: Path) -> None:
        logger = PipelineMetricsLogger(log_file=tmp_path / "e.jsonl")
        for name in ("pyright", "mypy", "npm-check", "type-check"):
            assert logger._infer_category(name) == "type"

    def test_infer_category_security(self, tmp_path: Path) -> None:
        logger = PipelineMetricsLogger(log_file=tmp_path / "e.jsonl")
        for name in ("bandit", "detect-secrets", "npm audit", "security-review"):
            assert logger._infer_category(name) == "security"

    def test_infer_category_test_default(self, tmp_path: Path) -> None:
        logger = PipelineMetricsLogger(log_file=tmp_path / "e.jsonl")
        assert logger._infer_category("pytest") == "test"
        assert logger._infer_category("jest") == "test"


# ---------------------------------------------------------------------------
# PipelineMetricsSummary
# ---------------------------------------------------------------------------


class TestPipelineMetricsSummary:
    def _write_events(self, path: Path, events: list[dict[str, object]]) -> None:
        with path.open("w") as fh:
            for e in events:
                fh.write(json.dumps(e) + "\n")

    def test_empty_log_returns_zero_counts(self, tmp_path: Path) -> None:
        log_file = tmp_path / "events.jsonl"
        log_file.write_text("")
        summary = PipelineMetricsSummary.from_log(log_file)
        assert summary.catches_per_stage["pre-commit"] == 0
        assert summary.catches_per_stage["ci"] == 0
        assert summary.catches_per_stage["ai-review"] == 0
        assert summary.false_positive_rate == 0.0

    def test_missing_log_returns_zero_counts(self, tmp_path: Path) -> None:
        summary = PipelineMetricsSummary.from_log(tmp_path / "nonexistent.jsonl")
        assert all(v == 0 for v in summary.catches_per_stage.values())

    def test_counts_failures_per_stage(self, tmp_path: Path) -> None:
        log_file = tmp_path / "events.jsonl"
        self._write_events(log_file, [
            {"stage": "pre-commit", "hook_name": "ruff", "category": "lint", "result": "fail", "affected_files": [], "pr_number": None, "timestamp": "2026-03-25T00:00:00+00:00"},
            {"stage": "pre-commit", "hook_name": "bandit", "category": "security", "result": "fail", "affected_files": [], "pr_number": None, "timestamp": "2026-03-25T00:00:00+00:00"},
            {"stage": "pre-commit", "hook_name": "ruff", "category": "lint", "result": "pass", "affected_files": [], "pr_number": None, "timestamp": "2026-03-25T00:00:00+00:00"},
            {"stage": "ci", "hook_name": "backend/pytest", "category": "test", "result": "fail", "affected_files": [], "pr_number": 1, "timestamp": "2026-03-25T00:00:00+00:00"},
            {"stage": "ai-review", "hook_name": "security-review", "category": "security", "result": "fail", "affected_files": [], "pr_number": 1, "timestamp": "2026-03-25T00:00:00+00:00"},
        ])
        summary = PipelineMetricsSummary.from_log(log_file)
        assert summary.catches_per_stage["pre-commit"] == 2
        assert summary.catches_per_stage["ci"] == 1
        assert summary.catches_per_stage["ai-review"] == 1

    def test_unique_catches_per_stage(self, tmp_path: Path) -> None:
        log_file = tmp_path / "events.jsonl"
        self._write_events(log_file, [
            {"stage": "pre-commit", "hook_name": "ruff", "category": "lint", "result": "fail", "affected_files": [], "pr_number": None, "timestamp": "2026-03-25T00:00:00+00:00"},
            {"stage": "pre-commit", "hook_name": "ruff", "category": "lint", "result": "fail", "affected_files": [], "pr_number": None, "timestamp": "2026-03-25T00:00:00+00:00"},
            {"stage": "pre-commit", "hook_name": "bandit", "category": "security", "result": "fail", "affected_files": [], "pr_number": None, "timestamp": "2026-03-25T00:00:00+00:00"},
        ])
        summary = PipelineMetricsSummary.from_log(log_file)
        assert summary.unique_catches_per_stage["pre-commit"] == {"ruff", "bandit"}

    def test_false_positive_rate_all_unconfirmed(self, tmp_path: Path) -> None:
        """AI review failures with no matching pre-commit/CI failures."""
        log_file = tmp_path / "events.jsonl"
        self._write_events(log_file, [
            {"stage": "ai-review", "hook_name": "code-review", "category": "lint", "result": "fail", "affected_files": [], "pr_number": 1, "timestamp": "2026-03-25T00:00:00+00:00"},
            {"stage": "ai-review", "hook_name": "security-review", "category": "security", "result": "fail", "affected_files": [], "pr_number": 1, "timestamp": "2026-03-25T00:00:00+00:00"},
        ])
        summary = PipelineMetricsSummary.from_log(log_file)
        assert summary.false_positive_rate == 1.0

    def test_false_positive_rate_none_unconfirmed(self, tmp_path: Path) -> None:
        """AI review failures all corroborated by CI."""
        log_file = tmp_path / "events.jsonl"
        self._write_events(log_file, [
            {"stage": "ci", "hook_name": "security-review", "category": "security", "result": "fail", "affected_files": [], "pr_number": 1, "timestamp": "2026-03-25T00:00:00+00:00"},
            {"stage": "ai-review", "hook_name": "security-review", "category": "security", "result": "fail", "affected_files": [], "pr_number": 1, "timestamp": "2026-03-25T00:00:00+00:00"},
        ])
        summary = PipelineMetricsSummary.from_log(log_file)
        assert summary.false_positive_rate == 0.0

    def test_false_positive_rate_no_ai_reviews(self, tmp_path: Path) -> None:
        log_file = tmp_path / "events.jsonl"
        self._write_events(log_file, [
            {"stage": "pre-commit", "hook_name": "ruff", "category": "lint", "result": "fail", "affected_files": [], "pr_number": None, "timestamp": "2026-03-25T00:00:00+00:00"},
        ])
        summary = PipelineMetricsSummary.from_log(log_file)
        assert summary.false_positive_rate == 0.0

    def test_skips_malformed_lines(self, tmp_path: Path) -> None:
        log_file = tmp_path / "events.jsonl"
        log_file.write_text('{"stage": "pre-commit", "result": "fail", "hook_name": "ruff", "category": "lint", "affected_files": [], "pr_number": null, "timestamp": "2026-03-25T00:00:00+00:00"}\nnot-valid-json\n')
        summary = PipelineMetricsSummary.from_log(log_file)
        assert summary.catches_per_stage["pre-commit"] == 1
