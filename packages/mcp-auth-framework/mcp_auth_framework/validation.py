"""Input validation utilities for OAuth endpoints."""

import json
import re
from typing import Any

# Input validation pattern for OAuth identifiers (client_id, device_code, etc.)
# Alphanumeric, hyphens, and underscores only, 1-256 characters
VALID_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,256}$")


def validate_client_id(client_id: str) -> bool:
    """Validate client_id format to prevent injection attacks.

    Args:
        client_id: The client identifier to validate

    Returns:
        True if valid, False otherwise

    Valid client IDs must:
    - Contain only alphanumeric characters, hyphens, and underscores
    - Be between 1 and 256 characters long
    """
    return bool(VALID_ID_PATTERN.match(client_id))


def parse_json_field(value: Any, default: Any) -> Any:
    """Parse a JSON string field, returning the value as-is if not a string.

    Args:
        value: The value to parse (may be a JSON string, list, or other type)
        default: Default value to return if parsing fails or value is falsy

    Returns:
        Parsed value or default
    """
    if not value:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def parse_scope_field(scopes: Any) -> str:
    """Parse OAuth scope field into a space-separated string.

    Handles multiple formats:
    - List of strings: ["read", "write"] -> "read write"
    - JSON string array: '["read", "write"]' -> "read write"
    - Space-separated string: "read write" -> "read write"

    Args:
        scopes: Scope value in any supported format

    Returns:
        Space-separated scope string
    """
    if not scopes:
        return "read"
    if isinstance(scopes, list):
        return " ".join(scopes)
    if isinstance(scopes, str) and scopes.startswith("["):
        try:
            parsed = json.loads(scopes)
            return " ".join(parsed) if isinstance(parsed, list) else scopes
        except json.JSONDecodeError:
            return scopes
    return scopes
