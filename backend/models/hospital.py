"""
models/hospital.py — Hospital registry Pydantic schemas.
"""

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Database model
# ---------------------------------------------------------------------------

class HospitalInDB(BaseModel):
    """
    Hospital document stored in MongoDB.

    `apiEndpoint`         — the base URL of this hospital's EHR API.
                            Used for inter-hospital exchange webhooks.
                            ⚠ HARDCODE WARNING: for now this is set manually
                            during seeding.  In production, hospitals register
                            via a secure onboarding flow.

    `tlsCertFingerprint`  — SHA-256 fingerprint of the hospital's TLS cert.
                            Used to verify the identity of the remote hospital
                            during exchange (certificate pinning).
                            ⚠ HARDCODE WARNING: set manually.  In production,
                            verify via a PKI or mutual TLS handshake.
    """
    id:                 str
    name:               str
    city:               str
    apiEndpoint:        str           # e.g. "https://hospital-a.example.com/api"
    tlsCertFingerprint: str           # SHA-256 hex fingerprint
    createdAt:          str


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

class HospitalResponse(BaseModel):
    """Same as HospitalInDB — all fields are safe to return."""
    id:                 str
    name:               str
    city:               str
    apiEndpoint:        str
    tlsCertFingerprint: str
    createdAt:          str
