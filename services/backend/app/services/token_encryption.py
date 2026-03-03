"""Token encryption service for securing OAuth tokens at rest.

Uses Fernet symmetric encryption with the application's secret key.
Key derivation uses HKDF (HMAC-based Key Derivation Function) with SHA-256
for cryptographically sound key material generation.

Note: Changing the key derivation from SHA-256 to HKDF is a breaking change.
Existing encrypted tokens stored in the database will be undecryptable with
the new key. Users with linked GitHub accounts will need to re-authenticate
via GitHub OAuth to generate a new token stored with the new key derivation.
"""

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import settings

# Static salt for HKDF — ensures deterministic key derivation from SECRET_KEY.
# This is intentionally a fixed value; randomness comes from the SECRET_KEY itself.
_HKDF_SALT = b"taskmanager-token-encryption-salt-v1"

# Info context string scopes this key exclusively to GitHub OAuth token encryption.
_HKDF_INFO = b"github-oauth-token-encryption"


def _get_encryption_key() -> bytes:
    """Derive a Fernet-compatible key from the application secret using HKDF.

    Uses HKDF (HMAC-based Key Derivation Function) with SHA-256 to derive a
    cryptographically sound 32-byte key from the application's SECRET_KEY.
    HKDF is a proper KDF that provides better security properties than a raw
    SHA-256 hash.

    Returns:
        A URL-safe base64-encoded 32-byte key suitable for use with Fernet.
    """
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_HKDF_SALT,
        info=_HKDF_INFO,
    )
    key_bytes = hkdf.derive(settings.secret_key.encode())
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
