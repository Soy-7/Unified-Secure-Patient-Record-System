"""
models/audit.py — Audit log Pydantic schemas.

Every write action and access denial is logged as an `AccessLogInDB` document.
Entries are chained via SHA-256 hashes (see crypto/hashing.py) so tampering
is detectable via GET /audit/verify.

Hash chain formula:
  entry_data    = f"{userId}{action}{resourceType}{resourceId}{timestamp}{details}"
  current_hash  = sha256_hex(prev_hash + entry_data)

The genesis entry uses prev_hash = "0" * 64 (64 zero chars).
"""

from enum import Enum

from pydantic import BaseModel


class AuditAction(str, Enum):
    """Action types logged in the audit trail."""
    VIEW            = "VIEW"
    CREATE          = "CREATE"
    UPDATE          = "UPDATE"
    DELETE          = "DELETE"
    SHARE           = "SHARE"
    EXPORT          = "EXPORT"
    LOGIN           = "LOGIN"
    LOGOUT          = "LOGOUT"
    ACCESS_DENIED   = "ACCESS_DENIED"


class AuditResourceType(str, Enum):
    """The type of entity the action was performed on."""
    record   = "record"
    patient  = "patient"
    user     = "user"
    hospital = "hospital"
    system   = "system"


# ---------------------------------------------------------------------------
# Database model
# ---------------------------------------------------------------------------

class AccessLogInDB(BaseModel):
    """
    Audit log entry stored in MongoDB.

    `hash`     — SHA-256(prevHash + entry_data) for this entry
    `prevHash` — hash of the immediately preceding audit entry
                 (genesis value: "0" * 64)

    Both fields together form the append-only hash chain.
    Modifying or deleting any past entry breaks the chain and is detected
    by GET /audit/verify.
    """
    id:           str
    userId:       str
    userName:     str
    userRole:     str
    action:       AuditAction
    resourceType: AuditResourceType
    resourceId:   str                   # ID of the resource acted on ("system" for auth events)
    hospitalId:   str
    ipAddress:    str
    timestamp:    str                   # ISO-8601
    hash:         str                   # SHA-256 hex of this entry
    prevHash:     str                   # SHA-256 hex of previous entry
    details:      str                   # human-readable description


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

class AccessLogResponse(BaseModel):
    """Same as AccessLogInDB — all fields are safe to return."""
    id:           str
    userId:       str
    userName:     str
    userRole:     str
    action:       AuditAction
    resourceType: AuditResourceType
    resourceId:   str
    hospitalId:   str
    ipAddress:    str
    timestamp:    str
    hash:         str
    prevHash:     str
    details:      str
