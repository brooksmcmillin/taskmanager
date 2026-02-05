"""Token encryption service for securing OAuth tokens at rest.

Uses Fernet symmetric encryption with the application's secret key.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _get_encryption_key() -> bytes:
    """Derive a Fernet-compatible key from the application secret.

    Fernet requires a 32-byte base64-encoded key. We derive this from
    the application's SECRET_KEY using SHA-256.
    """
    # Hash the secret key to get exactly 32 bytes
    key_bytes = hashlib.sha256(settings.secret_key.encode()).digest()
    # Base64 encode for Fernet compatibility
    return base64.urlsafe_b64encode(key_bytes)


def encrypt_token(token: str) -> str:
    """Encrypt an OAuth token for secure storage.

    Args:
        token: The plain text OAuth token

    Returns:
        The encrypted token as a string (base64 encoded)
    """
    if not token:
        return ""

    fernet = Fernet(_get_encryption_key())
    encrypted = fernet.encrypt(token.encode())
    return encrypted.decode()


def decrypt_token(encrypted_token: str) -> str | None:
    """Decrypt an OAuth token.

    Args:
        encrypted_token: The encrypted token string

    Returns:
        The decrypted token, or None if decryption fails
    """
    if not encrypted_token:
        return None

    try:
        fernet = Fernet(_get_encryption_key())
        decrypted = fernet.decrypt(encrypted_token.encode())
        return decrypted.decode()
    except (InvalidToken, ValueError):
        # Token is invalid or corrupted
        return None
