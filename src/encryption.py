"""Fernet-based encryption for user API keys stored in the database.

Uses a single ENCRYPTION_KEY env var (base64-encoded Fernet key).
Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import os

from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Fernet:
    """Get a Fernet instance from the ENCRYPTION_KEY env var."""
    key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY not set. Generate one with:\n"
            '  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode())


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return the ciphertext as a UTF-8 string."""
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a ciphertext string back to plaintext."""
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise ValueError("Decryption failed — ENCRYPTION_KEY may have changed. User must re-enter API keys.")
