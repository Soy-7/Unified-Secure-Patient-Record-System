"""
models/consent.py — Patient consent Pydantic schemas.

A consent record grants a specific user or hospital permission to access
one or more of a patient's records for a defined time window.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------

class ConsentCreate(BaseModel):
    """
    Submitted when a patient (or doctor on their behalf) grants consent.

    `grantedTo`     — the ID of the user or hospital receiving consent
    `grantedToType` — whether grantedTo is a "user" or "hospital"
    `recordIds`     — list of specific record IDs, or ["*"] to grant
                      access to all records for this patient
    `permissions`   — what the grantee can do: read, write, share
    `validFrom` / `validUntil` — ISO-8601 strings defining the consent window
    """
    patientId:    str
    grantedTo:    str
    grantedToType: Literal["user", "hospital"]
    recordIds:    list[str]                         = Field(default_factory=list)
    permissions:  list[Literal["read", "write", "share"]] = Field(default_factory=list)
    validFrom:    str                               # ISO-8601
    validUntil:   str                               # ISO-8601


# ---------------------------------------------------------------------------
# Database model
# ---------------------------------------------------------------------------

class ConsentInDB(BaseModel):
    """
    Consent document as stored in MongoDB.

    `isRevoked`  — set to True when a patient withdraws consent
    `revokedAt`  — ISO-8601 timestamp of revocation (None if still active)
    """
    id:            str
    patientId:     str
    grantedTo:     str
    grantedToType: str
    recordIds:     list[str]
    permissions:   list[str]
    validFrom:     str
    validUntil:    str
    isRevoked:     bool             = False
    revokedAt:     Optional[str]    = None
    createdAt:     str


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

class ConsentResponse(BaseModel):
    """Same as ConsentInDB — all fields are safe to expose."""
    id:            str
    patientId:     str
    grantedTo:     str
    grantedToType: str
    recordIds:     list[str]
    permissions:   list[str]
    validFrom:     str
    validUntil:    str
    isRevoked:     bool
    revokedAt:     Optional[str]
    createdAt:     str
