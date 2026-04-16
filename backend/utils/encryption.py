"""Simple symmetric encryption utilities for sensitive data at rest."""

from cryptography.fernet import Fernet, InvalidToken

from backend.utils.helpers import get_data_path


def _get_or_create_key() -> bytes:
    key_path = get_data_path() / ".encryption_key"
    if key_path.exists():
        return key_path.read_bytes().strip()
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    key_path.chmod(0o600)
    return key


_fernet = Fernet(_get_or_create_key())


def encrypt_value(value: str) -> str:
    """Encrypt a string value. Returns empty string for empty input."""
    if not value:
        return ""
    return _fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(value: str) -> str:
    """Decrypt a string value.

    If decryption fails (e.g. value was stored in plaintext before encryption
    was introduced), the original value is returned as-is for backward compatibility.
    """
    if not value:
        return ""
    try:
        return _fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return value
