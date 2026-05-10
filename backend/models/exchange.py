"""
models/exchange.py — Inter-hospital record exchange Pydantic schemas.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ExchangeStatus(str, Enum):
    """Lifecycle states of an exchange request."""
    pending   = "pending"
    approved  = "approved"
    rejected  = "rejected"
    completed = "completed"


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------

class ExchangeRequestCreate(BaseModel):
    """
    Submitted by a doctor/admin at the requesting hospital to ask
    the target hospital to share records for a given patient.

    `recordTypes` — which types of records are being requested,
    e.g. ["lab_result", "imaging"].  The target hospital decides
    which specific records to include when approving.
    """
    toHospitalId: str
    patientId:    str
    recordTypes:  list[str]   = Field(default_factory=list)
    purpose:      str


# ---------------------------------------------------------------------------
# Database model
# ---------------------------------------------------------------------------

class ExchangeRequestInDB(BaseModel):
    """
    Exchange request document stored in MongoDB.

    `encryptedPayload` — when the target hospital approves the request,
    the records are ECDH-encrypted and stored here so the requesting
    hospital can retrieve them.  See crypto/ecdh.py and ARCHITECTURE.md.
    """
    id:               str
    fromHospitalId:   str
    toHospitalId:     str
    patientId:        str
    requestedBy:      str               # user id of the doctor who made the request
    status:           ExchangeStatus    = ExchangeStatus.pending
    recordTypes:      list[str]         = Field(default_factory=list)
    purpose:          str
    encryptedPayload: Optional[str]     = None
    createdAt:        str
    resolvedAt:       Optional[str]     = None


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

class ExchangeRequestResponse(BaseModel):
    """Same as ExchangeRequestInDB — all fields are safe to return."""
    id:               str
    fromHospitalId:   str
    toHospitalId:     str
    patientId:        str
    requestedBy:      str
    status:           ExchangeStatus
    recordTypes:      list[str]
    purpose:          str
    encryptedPayload: Optional[str]
    createdAt:        str
    resolvedAt:       Optional[str]
