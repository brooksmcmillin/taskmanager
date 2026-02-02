"""Security utilities for password hashing and token generation."""

import re
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt

from app.config import settings


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Compatible with Node.js bcryptjs hashes.
    """
    # Convert password to bytes
    password_bytes = password.encode("utf-8")
    # Generate salt and hash
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    hashed = bcrypt.hashpw(password_bytes, salt)
    # Return as string
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash.

    Compatible with hashes created by Node.js bcryptjs.
    """
    try:
        password_bytes = plain_password.encode("utf-8")
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception:
        return False


def generate_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_hex(length)


def generate_session_id() -> str:
    """Generate a session ID."""
    return generate_token(32)


def generate_user_code() -> str:
    """Generate a user-friendly device code (e.g., WDJB-MJHT).

    Uses consonants only to avoid ambiguous characters and offensive words.
    """
    chars = "BCDFGHJKLMNPQRSTVWXZ"
    code = "".join(secrets.choice(chars) for _ in range(8))
    return f"{code[:4]}-{code[4:]}"


def validate_password_strength(password: str) -> bool:
    """Check if password meets complexity requirements.

    Must contain at least 2 of: lowercase, uppercase, numbers, special chars.
    """
    checks = [
        bool(re.search(r"[a-z]", password)),
        bool(re.search(r"[A-Z]", password)),
        bool(re.search(r"[0-9]", password)),
        bool(re.search(r"[^a-zA-Z0-9]", password)),
    ]
    return sum(checks) >= 2


def get_session_expiry() -> datetime:
    """Get session expiry datetime."""
    return datetime.now(UTC) + timedelta(days=settings.session_duration_days)


def get_token_expiry(seconds: int | None = None) -> datetime:
    """Get token expiry datetime."""
    expiry_seconds = seconds if seconds is not None else settings.access_token_expiry
    return datetime.now(UTC) + timedelta(seconds=expiry_seconds)


# API Key constants
API_KEY_PREFIX = "tm_"  # pragma: allowlist secret
API_KEY_LENGTH = 48  # 48 hex chars = 24 bytes of entropy


def generate_api_key() -> str:
    """Generate a new API key.

    Returns a key in format: tm_ + 48 hex characters.
    Example: tm_abc123def456...
    """
    random_part = secrets.token_hex(API_KEY_LENGTH // 2)
    return f"{API_KEY_PREFIX}{random_part}"


def get_api_key_prefix(key: str) -> str:
    """Get the display prefix of an API key.

    Returns the first 11 characters (tm_ + 8 hex chars) for display.
    """
    return key[:11]


def is_api_key(token: str) -> bool:
    """Check if a token is an API key (starts with tm_)."""
    return token.startswith(API_KEY_PREFIX)
