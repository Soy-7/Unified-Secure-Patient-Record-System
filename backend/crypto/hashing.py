"""
crypto/hashing.py — Password hashing and audit chain utilities.

Two separate concerns in one module:

1. PASSWORD HASHING — bcrypt via passlib
   Never SHA-256 for passwords. bcrypt is intentionally slow and has a cost
   factor (rounds=12) that can be increased as hardware improves.

2. AUDIT CHAIN HASHING — SHA-256 via hashlib
   Each audit log entry hashes its own content concatenated with the
   previous entry's hash.  Tampering with any entry breaks all subsequent
   hashes and is detectable via GET /audit/verify.
"""

import hashlib

from passlib.context import CryptContext

# ---------------------------------------------------------------------------
# bcrypt context
# rounds=12 is the cost factor — takes ~100ms per hash, which is
# intentionally slow to resist brute-force attacks.
# ⚠ HARDCODE WARNING: rounds=12 is fine for this project.
# In production, consider 13-14 if server load allows.
# ---------------------------------------------------------------------------
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(password: str) -> str:
    """
    Hash a plaintext password with bcrypt (cost factor 12).

    Args:
        password: The raw plaintext password from the user.

    Returns:
        A bcrypt hash string, e.g. "$2b$12$KIXt3dY1H5r5..."
        Safe to store in the database.
    """
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plaintext password against a stored bcrypt hash.

    Args:
        plain:  The password entered by the user.
        hashed: The bcrypt hash stored in the database.

    Returns:
        True if the password matches, False otherwise.
        Always runs in constant time to prevent timing attacks.
    """
    return _pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# SHA-256 utilities
# ---------------------------------------------------------------------------

def sha256_hex(data: str) -> str:
    """
    Compute the SHA-256 hash of a UTF-8 string.

    Args:
        data: Any string.

    Returns:
        64-character lowercase hex string.

    Example:
        sha256_hex("hello") → "2cf24dba5fb0a30e..."
    """
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def compute_audit_hash(prev_hash: str, entry_data: str) -> str:
    """
    Compute the hash for a new audit log entry.

    Chain formula (from idea.md):
        current_hash = SHA-256(prev_hash + entry_data)

    The genesis entry (very first log entry) should use:
        prev_hash = "0" * 64

    Args:
        prev_hash:  The `hash` field of the immediately previous audit entry.
        entry_data: A string representation of the current entry's data,
                    e.g. f"{userId}{action}{resourceId}{timestamp}{details}"

    Returns:
        64-character hex SHA-256 hash for this entry.
    """
    return sha256_hex(prev_hash + entry_data)


# ---------------------------------------------------------------------------
# Audit chain genesis constant
# ---------------------------------------------------------------------------

AUDIT_GENESIS_HASH: str = "0" * 64
"""
The prevHash value for the very first audit log entry in the system.
64 zero characters — a conventional genesis marker for hash chains.
"""
