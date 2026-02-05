"""Tests for the MCP Email Server."""

from mcp_email.server import (
    _is_recipient_allowed,
    _sanitize_html,
    _validate_email,
    _validate_email_list,
)


class TestEmailValidation:
    """Tests for email validation functions."""

    def test_validate_email_valid(self) -> None:
        """Test valid email addresses."""
        assert _validate_email("user@example.com") is True
        assert _validate_email("user.name@example.com") is True
        assert _validate_email("user+tag@example.com") is True
        assert _validate_email("user@sub.example.com") is True

    def test_validate_email_invalid(self) -> None:
        """Test invalid email addresses."""
        assert _validate_email("") is False
        assert _validate_email("notanemail") is False
        assert _validate_email("@example.com") is False
        assert _validate_email("user@") is False
        assert _validate_email("user@@example.com") is False

    def test_validate_email_list(self) -> None:
        """Test validating a list of emails."""
        valid, invalid = _validate_email_list(["user@example.com", "other@test.com"])
        assert valid is True
        assert invalid == []

        valid, invalid = _validate_email_list(["user@example.com", "invalid"])
        assert valid is False
        assert invalid == ["invalid"]


class TestRecipientAllowlist:
    """Tests for recipient allowlist functions."""

    def test_is_recipient_allowed_exact_match(self) -> None:
        """Test exact email matching."""
        patterns = ["user@example.com", "other@test.com"]
        assert _is_recipient_allowed("user@example.com", patterns) is True
        assert _is_recipient_allowed("USER@example.com", patterns) is True  # Case insensitive
        assert _is_recipient_allowed("other@test.com", patterns) is True
        assert _is_recipient_allowed("unknown@example.com", patterns) is False

    def test_is_recipient_allowed_wildcard(self) -> None:
        """Test wildcard domain matching."""
        patterns = ["*@example.com"]
        assert _is_recipient_allowed("user@example.com", patterns) is True
        assert _is_recipient_allowed("anyone@example.com", patterns) is True
        assert _is_recipient_allowed("user@other.com", patterns) is False

    def test_is_recipient_allowed_mixed(self) -> None:
        """Test mixed exact and wildcard patterns."""
        patterns = ["admin@test.com", "*@example.com"]
        assert _is_recipient_allowed("admin@test.com", patterns) is True
        assert _is_recipient_allowed("user@example.com", patterns) is True
        assert _is_recipient_allowed("user@test.com", patterns) is False


class TestHtmlSanitization:
    """Tests for HTML sanitization."""

    def test_sanitize_html_safe_content(self) -> None:
        """Test that safe HTML content is not modified."""
        safe_html = "<p>Hello <strong>World</strong></p>"
        assert _sanitize_html(safe_html) == safe_html

    def test_sanitize_html_script_tag(self) -> None:
        """Test that script tags are escaped."""
        dangerous = "<script>alert('xss')</script>"
        result = _sanitize_html(dangerous)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_sanitize_html_event_handler(self) -> None:
        """Test that event handlers are escaped."""
        dangerous = '<img src="x" onerror="alert(1)">'
        result = _sanitize_html(dangerous)
        assert 'onerror="' not in result

    def test_sanitize_html_javascript_url(self) -> None:
        """Test that javascript: URLs are escaped (whole content is escaped)."""
        dangerous = '<a href="javascript:alert(1)">Click</a>'
        result = _sanitize_html(dangerous)
        # The entire content should be HTML-escaped when dangerous pattern detected
        assert "&lt;a" in result  # < is escaped
        assert "<a" not in result  # Original tag should not be present
