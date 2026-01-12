"""Tests for TaskManager SDK exceptions."""

import pytest

from taskmanager_sdk.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TaskManagerError,
    ValidationError,
)


class TestExceptionHierarchy:
    """Test exception hierarchy and inheritance."""

    def test_all_exceptions_inherit_from_base(self) -> None:
        """Test that all custom exceptions inherit from TaskManagerError."""
        exceptions = [
            AuthenticationError,
            AuthorizationError,
            NotFoundError,
            ValidationError,
            RateLimitError,
            ServerError,
            NetworkError,
        ]

        for exc_class in exceptions:
            assert issubclass(exc_class, TaskManagerError)

    def test_base_exception_inherits_from_exception(self) -> None:
        """Test that TaskManagerError inherits from Exception."""
        assert issubclass(TaskManagerError, Exception)


class TestTaskManagerError:
    """Test base TaskManagerError."""

    def test_raise_base_exception(self) -> None:
        """Test raising base TaskManagerError."""
        with pytest.raises(TaskManagerError) as exc_info:
            raise TaskManagerError("Base error")

        assert str(exc_info.value) == "Base error"

    def test_catch_base_exception(self) -> None:
        """Test catching base TaskManagerError catches all SDK exceptions."""
        with pytest.raises(TaskManagerError):
            raise AuthenticationError("Auth error")


class TestAuthenticationError:
    """Test AuthenticationError."""

    def test_raise_authentication_error(self) -> None:
        """Test raising AuthenticationError."""
        with pytest.raises(AuthenticationError) as exc_info:
            raise AuthenticationError("Invalid credentials")

        assert str(exc_info.value) == "Invalid credentials"
        assert isinstance(exc_info.value, TaskManagerError)

    def test_catch_authentication_error(self) -> None:
        """Test catching AuthenticationError."""
        try:
            raise AuthenticationError("Auth failed")
        except AuthenticationError as e:
            assert "Auth failed" in str(e)


class TestAuthorizationError:
    """Test AuthorizationError."""

    def test_raise_authorization_error(self) -> None:
        """Test raising AuthorizationError."""
        with pytest.raises(AuthorizationError) as exc_info:
            raise AuthorizationError("Forbidden")

        assert str(exc_info.value) == "Forbidden"
        assert isinstance(exc_info.value, TaskManagerError)


class TestNotFoundError:
    """Test NotFoundError."""

    def test_raise_not_found_error(self) -> None:
        """Test raising NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            raise NotFoundError("Resource not found")

        assert str(exc_info.value) == "Resource not found"
        assert isinstance(exc_info.value, TaskManagerError)


class TestValidationError:
    """Test ValidationError."""

    def test_raise_validation_error(self) -> None:
        """Test raising ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError("Invalid input")

        assert str(exc_info.value) == "Invalid input"
        assert isinstance(exc_info.value, TaskManagerError)


class TestRateLimitError:
    """Test RateLimitError."""

    def test_raise_rate_limit_error(self) -> None:
        """Test raising RateLimitError."""
        with pytest.raises(RateLimitError) as exc_info:
            raise RateLimitError("Too many requests")

        assert str(exc_info.value) == "Too many requests"
        assert isinstance(exc_info.value, TaskManagerError)


class TestServerError:
    """Test ServerError."""

    def test_raise_server_error(self) -> None:
        """Test raising ServerError."""
        with pytest.raises(ServerError) as exc_info:
            raise ServerError("Internal server error")

        assert str(exc_info.value) == "Internal server error"
        assert isinstance(exc_info.value, TaskManagerError)


class TestNetworkError:
    """Test NetworkError."""

    def test_raise_network_error(self) -> None:
        """Test raising NetworkError."""
        with pytest.raises(NetworkError) as exc_info:
            raise NetworkError("Connection failed")

        assert str(exc_info.value) == "Connection failed"
        assert isinstance(exc_info.value, TaskManagerError)


class TestExceptionMessages:
    """Test exception messages and formatting."""

    def test_exception_with_empty_message(self) -> None:
        """Test exception with empty message."""
        with pytest.raises(TaskManagerError) as exc_info:
            raise TaskManagerError("")

        assert str(exc_info.value) == ""

    def test_exception_with_multiline_message(self) -> None:
        """Test exception with multiline message."""
        message = "Error occurred\nLine 2\nLine 3"
        with pytest.raises(TaskManagerError) as exc_info:
            raise TaskManagerError(message)

        assert str(exc_info.value) == message

    def test_exception_repr(self) -> None:
        """Test exception representation."""
        error = AuthenticationError("Test error")
        repr_str = repr(error)
        assert "AuthenticationError" in repr_str
        assert "Test error" in repr_str
