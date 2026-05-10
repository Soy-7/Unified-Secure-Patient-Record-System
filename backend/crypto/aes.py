"""
crypto/aes.py — AES-256-GCM symmetric encryption/decryption.

Design decisions:
  • Key derivation: PBKDF2-HMAC-SHA256 (100,000 iterations) so the same
    human-readable password can be used without weakening security.
  • IV: 12 random bytes per encryption call — NEVER reused.
    Reusing an IV with the same key in GCM mode is catastrophic
    (it leaks the authentication key and allows forgery).
  • GCM mode: provides both confidentiality (encryption) AND integrity
    (authentication tag).  If anyone modifies the ciphertext, decryption
    raises InvalidTag and we know it was tampered with.

cryptography library GCM note:
  The `tag` (16 bytes) is obtained via `encryptor.tag` AFTER `finalize()`.
  We store it as a separate base64 field ("tag") in the returned dict and
  append it when building the decryptor.

⚠ HARDCODE WARNING:
  `settings.demo_encryption_password` is used as the password for key
  derivation.  A single password encrypts ALL records.  In production,
  use a unique DEK (Data Encryption Key) per record, wrapped by a KMS.
"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------

def derive_key_from_password(password: str, salt: bytes) -> bytes:
    """
    Derive a 32-byte AES-256 key from a human-readable password.

    Uses PBKDF2-HMAC-SHA256 with 100,000 iterations — deliberately slow
    to resist brute-force attacks if the salt+ciphertext leaks.

    Args:
        password: The master encryption password (from settings).
        salt:     16 random bytes.  Must be stored alongside the ciphertext
                  so the same key can be re-derived for decryption.
                  NEVER reuse the same salt for different passwords.

    Returns:
        32 bytes suitable as an AES-256 key.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,     # HARDCODE: NIST recommends >= 600,000 for SHA-256 in 2023.
                                # 100,000 is used here for demo performance.
                                # Increase to 600,000 before production.
    )
    return kdf.derive(password.encode("utf-8"))


# ---------------------------------------------------------------------------
# Encryption
# ---------------------------------------------------------------------------

def encrypt(plaintext: str, key_bytes: bytes) -> dict[str, str]:
    """
    Encrypt a plaintext string with AES-256-GCM.

    A fresh 12-byte IV is generated for every call.  This is critical —
    never pass an IV from outside; always let this function generate it.

    Args:
        plaintext:  The string to encrypt (e.g. record content JSON).
        key_bytes:  32-byte AES key (from derive_key_from_password).

    Returns:
        {
            "ciphertext": str  — base64 of the encrypted bytes (tag NOT included)
            "iv":         str  — base64 of the 12-byte IV
            "tag":        str  — base64 of the 16-byte GCM authentication tag
        }

    Note on AESGCM from the cryptography library:
        AESGCM.encrypt() returns ciphertext + tag concatenated.
        We split them: ciphertext = result[:-16], tag = result[-16:]
    """
    iv = os.urandom(12)  # 12 bytes = 96 bits (GCM recommended IV length)

    aesgcm     = AESGCM(key_bytes)
    ct_and_tag = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)

    # AESGCM appends the 16-byte tag to the ciphertext
    ciphertext = ct_and_tag[:-16]
    tag        = ct_and_tag[-16:]

    return {
        "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
        "iv":         base64.b64encode(iv).decode("utf-8"),
        "tag":        base64.b64encode(tag).decode("utf-8"),
    }


# ---------------------------------------------------------------------------
# Decryption
# ---------------------------------------------------------------------------

def decrypt(ciphertext_b64: str, iv_b64: str, tag_b64: str, key_bytes: bytes) -> str:
    """
    Decrypt AES-256-GCM ciphertext back to a plaintext string.

    Raises cryptography.exceptions.InvalidTag if the ciphertext was
    tampered with — callers must handle this exception.

    Args:
        ciphertext_b64: base64-encoded ciphertext (tag NOT included).
        iv_b64:         base64-encoded 12-byte IV used during encryption.
        tag_b64:        base64-encoded 16-byte GCM authentication tag.
        key_bytes:      The same 32-byte key used for encryption.

    Returns:
        Original plaintext string.

    Raises:
        cryptography.exceptions.InvalidTag: if integrity check fails
            (ciphertext was modified, wrong key, or wrong IV).
    """
    ciphertext = base64.b64decode(ciphertext_b64)
    iv         = base64.b64decode(iv_b64)
    tag        = base64.b64decode(tag_b64)

    aesgcm     = AESGCM(key_bytes)
    plaintext  = aesgcm.decrypt(iv, ciphertext + tag, None)

    return plaintext.decode("utf-8")
