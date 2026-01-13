"""
Response validation helpers for MCP Resource server tools.

This module provides utilities for validating API responses and
generating consistent error responses in MCP tools.
"""

import json
import logging
from typing import Any

from taskmanager_sdk import ApiResponse

logger = logging.getLogger(__name__)


def json_error(message: str) -> str:
    """Create a JSON error response string.

    Args:
        message: Error message to include

    Returns:
        JSON string with {"error": message}
    """
    return json.dumps({"error": message})


def validate_list_response(
    response: ApiResponse, context: str, key: str | None = None
) -> tuple[list[dict[str, Any]], str | None]:
    """Validate that an API response contains a list of dictionaries.

    Args:
        response: The API response to validate
        context: Description of what we're fetching (e.g., "projects", "tasks")
        key: Optional key to extract list from wrapped response (e.g., "tasks" for {"tasks": [...]})

    Returns:
        Tuple of (validated list, error message or None)
    """
    if not response.success:
        return [], response.error or f"Failed to fetch {context}"

    data = response.data
    if data is None:
        return [], None  # Empty result, not an error

    # Handle wrapped responses like {"tasks": [...]} or {"categories": [...]}
    if isinstance(data, dict):
        # Try the provided key first, then the context as a key
        for k in [key, context, f"{context}s"]:
            if k and k in data:
                data = data[k]
                break
        else:
            # No matching key found - maybe it's a different structure
            error_msg = (
                f"Backend returned {context} as dict without expected key: {list(data.keys())}"
            )
            logger.error(error_msg)
            return [], error_msg

    if not isinstance(data, list):
        error_msg = (
            f"Backend returned invalid {context} format: expected list, got {type(data).__name__}"
        )
        logger.error(f"{error_msg}. Value: {data!r}")
        return [], error_msg

    # Validate each item is a dict
    validated = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                f"Invalid {context} item at index {i}: expected dict, got {type(item).__name__}. Skipping."
            )
            continue
        validated.append(item)

    return validated, None


def validate_dict_response(
    response: ApiResponse, context: str
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate that an API response contains a dictionary.

    Args:
        response: The API response to validate
        context: Description of what we're fetching (e.g., "task", "project")

    Returns:
        Tuple of (validated dict or None, error message or None)
    """
    if not response.success:
        return None, response.error or f"Failed to fetch {context}"

    data = response.data
    if data is None:
        return None, f"No {context} data returned from backend"

    if not isinstance(data, dict):
        error_msg = (
            f"Backend returned invalid {context} format: expected dict, got {type(data).__name__}"
        )
        logger.error(f"{error_msg}. Value: {data!r}")
        return None, error_msg

    return data, None


def require_list(
    response: ApiResponse, context: str, key: str | None = None
) -> list[dict[str, Any]] | str:
    """Validate list response, returning either the list or an error string.

    This is a convenience wrapper that returns a JSON error string directly
    if validation fails, making it suitable for use in MCP tools.

    Args:
        response: The API response to validate
        context: Description of what we're fetching
        key: Optional key to extract list from wrapped response

    Returns:
        Either the validated list, or a JSON error string
    """
    data, error = validate_list_response(response, context, key)
    if error:
        logger.error(f"Failed to get {context}: {error}")
        return json_error(error)
    return data


def require_dict(
    response: ApiResponse, context: str
) -> dict[str, Any] | str:
    """Validate dict response, returning either the dict or an error string.

    This is a convenience wrapper that returns a JSON error string directly
    if validation fails, making it suitable for use in MCP tools.

    Args:
        response: The API response to validate
        context: Description of what we're fetching

    Returns:
        Either the validated dict, or a JSON error string
    """
    data, error = validate_dict_response(response, context)
    if error:
        logger.error(f"Failed to get {context}: {error}")
        return json_error(error)
    if data is None:
        return json_error(f"No {context} data returned")
    return data
