"""Standardized API error definitions.

Maps error codes from the Node.js implementation to FastAPI exceptions.
"""

from typing import Any

from fastapi import HTTPException


class ApiError(HTTPException):
    """Custom API exception with error code."""

    def __init__(
        self,
        code: str,
        status_code: int,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.error_details = details
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message": message, "details": details},
        )


class Errors:
    """Factory for standardized API errors."""

    # =========================================================================
    # Authentication Errors (AUTH_001 - AUTH_004)
    # =========================================================================

    @staticmethod
    def invalid_credentials() -> ApiError:
        """AUTH_001: Invalid username or password."""
        return ApiError("AUTH_001", 401, "Invalid username or password")

    @staticmethod
    def auth_required() -> ApiError:
        """AUTH_002: Authentication required."""
        return ApiError("AUTH_002", 401, "Authentication required")

    @staticmethod
    def session_expired() -> ApiError:
        """AUTH_003: Session has expired."""
        return ApiError("AUTH_003", 401, "Session has expired")

    @staticmethod
    def invalid_token() -> ApiError:
        """AUTH_004: Invalid or expired token."""
        return ApiError("AUTH_004", 401, "Invalid or expired token")

    # =========================================================================
    # Authorization Errors (AUTHZ_001 - AUTHZ_003)
    # =========================================================================

    @staticmethod
    def permission_denied() -> ApiError:
        """AUTHZ_001: Permission denied."""
        return ApiError("AUTHZ_001", 403, "Permission denied")

    @staticmethod
    def not_owner() -> ApiError:
        """AUTHZ_002: Not the resource owner."""
        return ApiError("AUTHZ_002", 403, "You do not own this resource")

    @staticmethod
    def insufficient_scope(required: str) -> ApiError:
        """AUTHZ_003: Insufficient OAuth scope."""
        return ApiError(
            "AUTHZ_003",
            403,
            f"Insufficient scope. Required: {required}",
            {"required_scope": required},
        )

    # =========================================================================
    # Validation Errors (VALIDATION_001 - VALIDATION_008)
    # =========================================================================

    @staticmethod
    def required_field(field: str) -> ApiError:
        """VALIDATION_001: Required field missing."""
        return ApiError(
            "VALIDATION_001",
            400,
            f"{field} is required",
            {"field": field},
        )

    @staticmethod
    def invalid_email() -> ApiError:
        """VALIDATION_002: Invalid email format."""
        return ApiError("VALIDATION_002", 400, "Invalid email format")

    @staticmethod
    def password_too_short(min_length: int = 8) -> ApiError:
        """VALIDATION_003: Password too short."""
        return ApiError(
            "VALIDATION_003",
            400,
            f"Password must be at least {min_length} characters",
            {"min_length": min_length},
        )

    @staticmethod
    def password_too_weak() -> ApiError:
        """VALIDATION_004: Password doesn't meet complexity requirements."""
        return ApiError(
            "VALIDATION_004",
            400,
            "Password must contain at least 2 of: "
            "lowercase, uppercase, numbers, special characters",
        )

    @staticmethod
    def invalid_id(resource: str) -> ApiError:
        """VALIDATION_005: Invalid resource ID."""
        return ApiError(
            "VALIDATION_005",
            400,
            f"Invalid {resource} ID",
            {"resource": resource},
        )

    @staticmethod
    def invalid_date(field: str) -> ApiError:
        """VALIDATION_006: Invalid date format."""
        return ApiError(
            "VALIDATION_006",
            400,
            f"Invalid date format for {field}",
            {"field": field},
        )

    @staticmethod
    def field_too_long(field: str, max_length: int) -> ApiError:
        """VALIDATION_007: Field exceeds maximum length."""
        return ApiError(
            "VALIDATION_007",
            400,
            f"{field} exceeds maximum length of {max_length}",
            {"field": field, "max_length": max_length},
        )

    @staticmethod
    def invalid_value(field: str, allowed: list[str]) -> ApiError:
        """VALIDATION_008: Invalid value for field."""
        return ApiError(
            "VALIDATION_008",
            400,
            f"Invalid value for {field}. Allowed: {', '.join(allowed)}",
            {"field": field, "allowed": allowed},
        )

    @staticmethod
    def validation(message: str) -> ApiError:
        """VALIDATION_009: General validation error."""
        return ApiError("VALIDATION_009", 400, message)

    # =========================================================================
    # Not Found Errors (NOT_FOUND_001 - NOT_FOUND_005)
    # =========================================================================

    @staticmethod
    def not_found(resource: str) -> ApiError:
        """NOT_FOUND_001: Resource not found."""
        return ApiError(
            "NOT_FOUND_001",
            404,
            f"{resource} not found",
            {"resource": resource},
        )

    @staticmethod
    def user_not_found() -> ApiError:
        """NOT_FOUND_002: User not found."""
        return ApiError("NOT_FOUND_002", 404, "User not found")

    @staticmethod
    def todo_not_found() -> ApiError:
        """NOT_FOUND_003: Todo not found."""
        return ApiError("NOT_FOUND_003", 404, "Todo not found")

    @staticmethod
    def project_not_found() -> ApiError:
        """NOT_FOUND_004: Project not found."""
        return ApiError("NOT_FOUND_004", 404, "Project not found")

    @staticmethod
    def oauth_client_not_found() -> ApiError:
        """NOT_FOUND_005: OAuth client not found."""
        return ApiError("NOT_FOUND_005", 404, "OAuth client not found")

    @staticmethod
    def recurring_task_not_found() -> ApiError:
        """NOT_FOUND_006: Recurring task not found."""
        return ApiError("NOT_FOUND_006", 404, "Recurring task not found")

    @staticmethod
    def registration_code_not_found() -> ApiError:
        """NOT_FOUND_007: Registration code not found."""
        return ApiError("NOT_FOUND_007", 404, "Registration code not found")

    # =========================================================================
    # Conflict Errors (CONFLICT_001 - CONFLICT_002)
    # =========================================================================

    @staticmethod
    def username_exists() -> ApiError:
        """CONFLICT_001: Username already exists."""
        return ApiError("CONFLICT_001", 409, "Username already exists")

    @staticmethod
    def email_exists() -> ApiError:
        """CONFLICT_002: Email already exists."""
        return ApiError("CONFLICT_002", 409, "Email already exists")

    @staticmethod
    def registration_code_exists() -> ApiError:
        """CONFLICT_003: Registration code already exists."""
        return ApiError("CONFLICT_003", 409, "Registration code already exists")

    # =========================================================================
    # Registration Code Errors (REG_001 - REG_003)
    # =========================================================================

    @staticmethod
    def invalid_registration_code() -> ApiError:
        """REG_001: Invalid or expired registration code."""
        return ApiError("REG_001", 400, "Invalid or expired registration code")

    @staticmethod
    def registration_code_exhausted() -> ApiError:
        """REG_002: Registration code has reached maximum uses."""
        return ApiError("REG_002", 400, "Registration code has reached maximum uses")

    @staticmethod
    def registration_code_required() -> ApiError:
        """REG_003: Registration code is required."""
        return ApiError("REG_003", 400, "Registration code is required")

    # =========================================================================
    # Rate Limiting (RATE_001)
    # =========================================================================

    @staticmethod
    def rate_limited(retry_after: int | None = None) -> ApiError:
        """RATE_001: Too many requests."""
        details = {"retry_after": retry_after} if retry_after else None
        return ApiError("RATE_001", 429, "Too many requests", details)

    # =========================================================================
    # OAuth Errors (OAUTH_001 - OAUTH_010)
    # =========================================================================

    @staticmethod
    def oauth_invalid_client() -> ApiError:
        """OAUTH_001: Invalid client."""
        return ApiError("OAUTH_001", 401, "Invalid client_id or client_secret")

    @staticmethod
    def oauth_invalid_redirect() -> ApiError:
        """OAUTH_002: Invalid redirect URI."""
        return ApiError("OAUTH_002", 400, "Invalid redirect_uri")

    @staticmethod
    def oauth_invalid_scope() -> ApiError:
        """OAUTH_003: Invalid scope."""
        return ApiError("OAUTH_003", 400, "Invalid or unsupported scope")

    @staticmethod
    def oauth_invalid_grant() -> ApiError:
        """OAUTH_004: Invalid grant."""
        return ApiError("OAUTH_004", 400, "Invalid or expired authorization code")

    @staticmethod
    def oauth_invalid_token() -> ApiError:
        """OAUTH_005: Invalid token."""
        return ApiError("OAUTH_005", 401, "Invalid or expired access token")

    @staticmethod
    def oauth_access_denied() -> ApiError:
        """OAUTH_006: Access denied."""
        return ApiError("OAUTH_006", 403, "Access denied by resource owner")

    @staticmethod
    def oauth_unsupported_grant_type() -> ApiError:
        """OAUTH_007: Unsupported grant type."""
        return ApiError("OAUTH_007", 400, "Unsupported grant_type")

    @staticmethod
    def oauth_authorization_pending() -> ApiError:
        """OAUTH_008: Authorization pending (device flow)."""
        return ApiError("OAUTH_008", 400, "Authorization pending")

    @staticmethod
    def oauth_slow_down() -> ApiError:
        """OAUTH_009: Slow down polling (device flow)."""
        return ApiError("OAUTH_009", 400, "Slow down")

    @staticmethod
    def oauth_expired_token() -> ApiError:
        """OAUTH_010: Device code expired."""
        return ApiError("OAUTH_010", 400, "Device code has expired")

    # =========================================================================
    # Server Errors (SERVER_001 - SERVER_003)
    # =========================================================================

    @staticmethod
    def internal_error() -> ApiError:
        """SERVER_001: Internal server error."""
        return ApiError("SERVER_001", 500, "Internal server error")

    @staticmethod
    def database_error() -> ApiError:
        """SERVER_002: Database error."""
        return ApiError("SERVER_002", 500, "Database error")

    @staticmethod
    def service_unavailable() -> ApiError:
        """SERVER_003: Service unavailable."""
        return ApiError("SERVER_003", 503, "Service temporarily unavailable")


errors = Errors()
