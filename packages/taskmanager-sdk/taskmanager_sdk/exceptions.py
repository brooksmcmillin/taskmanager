class TaskManagerError(Exception):
    """Base exception for TaskManager SDK."""

    pass


class AuthenticationError(TaskManagerError):
    """Raised when authentication fails."""

    pass


class AuthorizationError(TaskManagerError):
    """Raised when authorization fails."""

    pass


class NotFoundError(TaskManagerError):
    """Raised when a resource is not found."""

    pass


class ValidationError(TaskManagerError):
    """Raised when request validation fails."""

    pass


class RateLimitError(TaskManagerError):
    """Raised when rate limit is exceeded."""

    pass


class ServerError(TaskManagerError):
    """Raised when server encounters an error."""

    pass


class NetworkError(TaskManagerError):
    """Raised when network communication fails."""

    pass
