"""
routers/crypto_demo.py — Encryption Lab demonstration endpoints.

Routes:
  POST /crypto/encrypt-demo — AES-256-GCM encrypt demo text
  POST /crypto/decrypt-demo — AES-256-GCM decrypt
  POST /crypto/ecdh-demo    — ECDH key exchange demo (two simulated hospitals)

No authentication required — these are for the Encryption Lab UI page.

⚠ These routes use the DEMO key only.
  They MUST NOT be used to encrypt real patient data.
  Real records use POST /records which encrypts server-side with the same
  key but through the proper, audited pipeline.
"""

import base64

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings
from crypto.aes import derive_key_from_password
from crypto.aes import decrypt as aes_decrypt
from crypto.aes import encrypt as aes_encrypt
from crypto.ecdh import derive_shared_secret, generate_keypair, get_key_fingerprint

router = APIRouter(prefix="/crypto", tags=["Crypto Demo"])

# HARDCODE: same static salt and password as records.py
_STATIC_SALT      = b"EHR-SALT-2024-STATIC"
_DEMO_PASSWORD    = "EHR-DEMO-KEY-2024"   # HARDCODE — read from settings in routes


def _get_demo_key() -> bytes:
    return derive_key_from_password(settings.demo_encryption_password, _STATIC_SALT)


# ---------------------------------------------------------------------------
# Request/response bodies
# ---------------------------------------------------------------------------

class EncryptRequest(BaseModel):
    text: str


class DecryptRequest(BaseModel):
    ciphertext: str  # base64(ciphertext + tag) combined
    iv:         str  # base64 of 12-byte IV


# ---------------------------------------------------------------------------
# POST /crypto/encrypt-demo
# ---------------------------------------------------------------------------

@router.post(
    "/encrypt-demo",
    summary="AES-256-GCM encrypt demo text (no auth)",
)
async def encrypt_demo(body: EncryptRequest) -> dict:
    """
    Encrypt a plaintext string with AES-256-GCM using the demo key.

    Returns the ciphertext (with tag appended) and IV as base64 strings.
    Pass these to /crypto/decrypt-demo to verify decryption.

    The `ciphertext` field in the response contains ciphertext+tag combined
    (same format as stored in the records collection).
    """
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="text cannot be empty")

    key = _get_demo_key()
    enc = aes_encrypt(body.text, key)

    # Combine ciphertext + tag for the response (mirrors records storage format)
    ct_bytes  = base64.b64decode(enc["ciphertext"])
    tag_bytes = base64.b64decode(enc["tag"])
    combined  = base64.b64encode(ct_bytes + tag_bytes).decode("utf-8")

    return {
        "ciphertext":  combined,
        "iv":          enc["iv"],
        "algorithm":   "AES-256-GCM",
        "keyLength":   256,
    }


# ---------------------------------------------------------------------------
# POST /crypto/decrypt-demo
# ---------------------------------------------------------------------------

@router.post(
    "/decrypt-demo",
    summary="AES-256-GCM decrypt demo ciphertext (no auth)",
)
async def decrypt_demo(body: DecryptRequest) -> dict:
    """
    Decrypt a ciphertext produced by /crypto/encrypt-demo.

    Expects:
      ciphertext — base64(ciphertext_bytes + tag_bytes) combined
      iv         — base64 of the 12-byte IV returned from encrypt-demo
    """
    key = _get_demo_key()

    try:
        ct_and_tag = base64.b64decode(body.ciphertext)
        ct_b64     = base64.b64encode(ct_and_tag[:-16]).decode("utf-8")
        tag_b64    = base64.b64encode(ct_and_tag[-16:]).decode("utf-8")
        plaintext  = aes_decrypt(ct_b64, body.iv, tag_b64, key)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Decryption failed — ciphertext may be corrupted or IV is wrong",
        )

    return {"plaintext": plaintext}


# ---------------------------------------------------------------------------
# POST /crypto/ecdh-demo
# ---------------------------------------------------------------------------

@router.post(
    "/ecdh-demo",
    summary="ECDH P-256 key exchange demo (no auth)",
)
async def ecdh_demo() -> dict:
    """
    Simulate an ECDH key exchange between two hospitals.

    1. Both hospitals generate fresh P-256 key pairs
    2. Hospital A derives shared secret using: its private key + B's public key
    3. Hospital B derives shared secret using: its private key + A's public key
    4. Both shared secrets are mathematically identical (ECDH property)

    Returns public keys, fingerprints, whether the secrets match,
    and a preview of the shared secret (first 16 chars + "...").

    Note: Private keys are generated fresh per request and NOT stored anywhere.
    This is a stateless demonstration only.
    """
    keys_a = generate_keypair()
    keys_b = generate_keypair()

    secret_a = derive_shared_secret(keys_a["privateKey"], keys_b["publicKey"])
    secret_b = derive_shared_secret(keys_b["privateKey"], keys_a["publicKey"])

    return {
        "hospitalA": {
            "publicKey":   keys_a["publicKey"],
            "fingerprint": get_key_fingerprint(keys_a["publicKey"]),
        },
        "hospitalB": {
            "publicKey":   keys_b["publicKey"],
            "fingerprint": get_key_fingerprint(keys_b["publicKey"]),
        },
        "sharedSecretMatch":   secret_a == secret_b,
        "sharedSecretPreview": secret_a[:16] + "...",
    }
