"""Tests for Lakera Guard fail-open/fail-closed configuration."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest

import mcp_resource_framework.security.lakera_guard as lakera_module
from mcp_resource_framework.security.lakera_guard import (
    LakeraGuardError,
    _screen_and_handle,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CLEAN_RESPONSE: dict = {"results": [{"flagged": False, "categories": {}}]}

_FLAGGED_RESPONSE: dict = {
    "results": [
        {
            "flagged": True,
            "categories": {"prompt_injection": True},
        }
    ]
}


# ---------------------------------------------------------------------------
# Tests for _screen_and_handle – fail-open / fail-closed on HTTPError
# ---------------------------------------------------------------------------


class TestFailOpenConfig:
    """LAKERA_FAIL_OPEN controls what happens when the API raises HTTPError."""

    @pytest.mark.asyncio
    async def test_fail_open_true_allows_request_on_http_error(self) -> None:
        """When LAKERA_FAIL_OPEN=true, HTTPError should NOT raise; request passes."""
        http_error = httpx.HTTPStatusError(
            "503 Service Unavailable",
            request=httpx.Request("POST", "https://api.lakera.ai/v2/guard"),
            response=httpx.Response(503),
        )
        with (
            patch.object(lakera_module, "LAKERA_FAIL_OPEN", True),
            patch(
                "mcp_resource_framework.security.lakera_guard.screen_content",
                new_callable=AsyncMock,
                side_effect=http_error,
            ),
        ):
            # Should not raise
            await _screen_and_handle(
                content="some user input",
                role="user",
                context="test context",
                block_on_detection=True,
            )

    @pytest.mark.asyncio
    async def test_fail_closed_false_rejects_request_on_http_error(self) -> None:
        """When LAKERA_FAIL_OPEN=false (default), HTTPError should raise LakeraGuardError."""
        http_error = httpx.HTTPStatusError(
            "503 Service Unavailable",
            request=httpx.Request("POST", "https://api.lakera.ai/v2/guard"),
            response=httpx.Response(503),
        )
        with (
            patch.object(lakera_module, "LAKERA_FAIL_OPEN", False),
            patch(
                "mcp_resource_framework.security.lakera_guard.screen_content",
                new_callable=AsyncMock,
                side_effect=http_error,
            ),
            pytest.raises(LakeraGuardError, match="Lakera Guard API unavailable"),
        ):
            await _screen_and_handle(
                content="some user input",
                role="user",
                context="test context",
                block_on_detection=True,
            )

    @pytest.mark.asyncio
    async def test_default_behavior_is_fail_closed(self) -> None:
        """The module-level LAKERA_FAIL_OPEN default must be False (fail-closed)."""
        # Read the actual constant from the module (not patched)
        assert lakera_module.LAKERA_FAIL_OPEN is False, (
            "LAKERA_FAIL_OPEN must default to False for production safety"
        )

    @pytest.mark.asyncio
    async def test_fail_open_logs_warning_not_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """In fail-open mode, the log message should be WARNING level."""
        http_error = httpx.ConnectError("Connection refused")
        log_name = "mcp_resource_framework.security.lakera_guard"
        with (
            patch.object(lakera_module, "LAKERA_FAIL_OPEN", True),
            patch(
                "mcp_resource_framework.security.lakera_guard.screen_content",
                new_callable=AsyncMock,
                side_effect=http_error,
            ),
            caplog.at_level(logging.WARNING, logger=log_name),
        ):
            await _screen_and_handle(
                content="test content",
                role="user",
                context="unit test",
                block_on_detection=True,
            )

        assert any("LAKERA_FAIL_OPEN=true" in record.message for record in caplog.records)
        # Must be WARNING, not ERROR
        warning_records = [r for r in caplog.records if "LAKERA_FAIL_OPEN=true" in r.message]
        assert all(r.levelname == "WARNING" for r in warning_records)

    @pytest.mark.asyncio
    async def test_fail_closed_logs_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """In fail-closed mode, the log message should be ERROR level."""
        http_error = httpx.ConnectError("Connection refused")
        log_name = "mcp_resource_framework.security.lakera_guard"
        with (
            patch.object(lakera_module, "LAKERA_FAIL_OPEN", False),
            patch(
                "mcp_resource_framework.security.lakera_guard.screen_content",
                new_callable=AsyncMock,
                side_effect=http_error,
            ),
            caplog.at_level(logging.ERROR, logger=log_name),
            pytest.raises(LakeraGuardError),
        ):
            await _screen_and_handle(
                content="test content",
                role="user",
                context="unit test",
                block_on_detection=True,
            )

        assert any("LAKERA_FAIL_OPEN=false" in record.message for record in caplog.records)
        error_records = [r for r in caplog.records if "LAKERA_FAIL_OPEN=false" in r.message]
        assert all(r.levelname == "ERROR" for r in error_records)

    @pytest.mark.asyncio
    async def test_fail_open_network_error_allows_request(self) -> None:
        """Fail-open applies to network errors (ConnectError) as well as HTTP errors."""
        with (
            patch.object(lakera_module, "LAKERA_FAIL_OPEN", True),
            patch(
                "mcp_resource_framework.security.lakera_guard.screen_content",
                new_callable=AsyncMock,
                side_effect=httpx.ConnectError("timeout"),
            ),
        ):
            # Should not raise
            await _screen_and_handle(
                content="some content",
                role="user",
                context="network test",
                block_on_detection=True,
            )

    @pytest.mark.asyncio
    async def test_fail_closed_network_error_rejects_request(self) -> None:
        """Fail-closed applies to network errors (ConnectError) as well as HTTP errors."""
        with (
            patch.object(lakera_module, "LAKERA_FAIL_OPEN", False),
            patch(
                "mcp_resource_framework.security.lakera_guard.screen_content",
                new_callable=AsyncMock,
                side_effect=httpx.ConnectError("timeout"),
            ),
            pytest.raises(LakeraGuardError),
        ):
            await _screen_and_handle(
                content="some content",
                role="user",
                context="network test",
                block_on_detection=True,
            )

    @pytest.mark.asyncio
    async def test_clean_content_passes_regardless_of_fail_mode(self) -> None:
        """When the API succeeds and content is clean, both modes allow the request."""
        for fail_open in (True, False):
            with (
                patch.object(lakera_module, "LAKERA_FAIL_OPEN", fail_open),
                patch(
                    "mcp_resource_framework.security.lakera_guard.screen_content",
                    new_callable=AsyncMock,
                    return_value=_CLEAN_RESPONSE,
                ),
            ):
                # Should not raise in either mode
                await _screen_and_handle(
                    content="safe content",
                    role="user",
                    context="clean content test",
                    block_on_detection=True,
                )

    @pytest.mark.asyncio
    async def test_flagged_content_always_blocked_when_block_on_detection_true(
        self,
    ) -> None:
        """Flagged content is blocked regardless of LAKERA_FAIL_OPEN when block_on_detection."""
        for fail_open in (True, False):
            with (
                patch.object(lakera_module, "LAKERA_FAIL_OPEN", fail_open),
                patch(
                    "mcp_resource_framework.security.lakera_guard.screen_content",
                    new_callable=AsyncMock,
                    return_value=_FLAGGED_RESPONSE,
                ),
                pytest.raises(LakeraGuardError, match="prompt_injection"),
            ):
                await _screen_and_handle(
                    content="inject this",
                    role="user",
                    context="flagged content test",
                    block_on_detection=True,
                )
