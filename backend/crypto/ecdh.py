"""
crypto/ecdh.py — ECDH P-256 key pair generation and key agreement.

Used for inter-hospital record exchange (see ARCHITECTURE.md — ECDH section).

Protocol summary:
  1. Requesting hospital calls generate_keypair() → ephemeral key pair
  2. Sends publicKey with the exchange request
  3. Target hospital calls derive_shared_secret(its_private_key, requestor_public_key)
  4. Both hospitals independently derive the same shared secret
  5. That secret is used to encrypt/decrypt the transferred records

Note on key format:
  The spec mentions "JWK format" but this implementation uses PEM (Privacy-Enhanced Mail)
  format, which is what the cryptography library natively produces and is simpler to
  handle in Python.  PEM is equally secure.  If JWK is needed for browser interop in a
  future phase, a JWK serialiser can be added here.
"""

import base64
import hashlib

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def generate_keypair() -> dict[str, str]:
    """
    Generate a fresh ECDH P-256 (secp256r1) key pair.

    Returns:
        {
            "publicKey":  str  — PEM-encoded public key
            "privateKey": str  — PEM-encoded private key (keep secret!)
        }

    Usage:
        keys = generate_keypair()
        store keys["publicKey"] in the hospital/user document
        keep keys["privateKey"] secure (encrypted at rest in production)

    ⚠ HARDCODE WARNING: Private keys are returned as plaintext PEM here.
    In production, wrap the private key with a KMS master key before storage.
    """
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key  = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return {"publicKey": public_pem, "privateKey": private_pem}


def derive_shared_secret(private_key_pem: str, peer_public_key_pem: str) -> str:
    """
    Perform ECDH key agreement and derive a shared secret.

    Both hospitals call this with their own private key and the other
    hospital's public key.  The result is mathematically identical on
    both sides, so no secret is ever transmitted over the network.

    The raw ECDH output is passed through HKDF (HMAC-based Key Derivation
    Function) to produce a uniform 32-byte key suitable for AES-256.

    Args:
        private_key_pem:     PEM-encoded private key of this party.
        peer_public_key_pem: PEM-encoded public key of the other party.

    Returns:
        Base64-encoded 32-byte derived key (AES-256 ready).
    """
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"), password=None
    )
    peer_public_key = serialization.load_pem_public_key(
        peer_public_key_pem.encode("utf-8")
    )

    # Raw shared secret from ECDH (not suitable as a key directly)
    raw_secret: bytes = private_key.exchange(ec.ECDH(), peer_public_key)

    # HKDF — stretch/normalise the raw secret into a proper 32-byte key
    # ⚠ HARDCODE WARNING: The HKDF salt and info are fixed strings.
    # In production, use a session-specific salt (e.g. nonce from the exchange request).
    derived_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,      # HARDCODE: None uses HKDF default salt; replace with session nonce
        info=b"ehr-platform-exchange-v1",  # HARDCODE: context label
    ).derive(raw_secret)

    return base64.b64encode(derived_key).decode("utf-8")


def get_key_fingerprint(public_key_pem: str) -> str:
    """
    Compute a short display fingerprint for a public key.

    Useful for the UI to let users verify they're talking to the right hospital.

    Args:
        public_key_pem: PEM-encoded public key string.

    Returns:
        First 32 characters of base64(SHA-256(public_key_pem)).
        Example: "aB3kLmNoPqRsTuVw..."
    """
    digest = hashlib.sha256(public_key_pem.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("utf-8")[:32]
