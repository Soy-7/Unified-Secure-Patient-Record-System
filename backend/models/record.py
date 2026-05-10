"""
models/record.py — Medical record Pydantic schemas.

The content of every record is encrypted before being stored (AES-256-GCM).
Only the metadata fields (recordType, title, tags, accessPolicy) are stored
in plaintext so MongoDB can filter without decrypting every document.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RecordType(str, Enum):
    """Supported medical record types."""
    diagnosis           = "diagnosis"
    prescription        = "prescription"
    lab_result          = "lab_result"
    imaging             = "imaging"
    discharge_summary   = "discharge_summary"
    consultation        = "consultation"


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------

class RecordCreate(BaseModel):
    """
    Submitted by a doctor when creating a new record.

    `content` — the plaintext data that will be AES-256-GCM encrypted
    before storage.  Never stored as-is.

    `accessPolicy` — list of CP-ABE style attributes required to decrypt,
    e.g. ["doctor", "hospital-001"].  A user needs ALL listed attributes
    to access the record.  Server-side check only — never trust the frontend.
    """
    patientId:     str
    hospitalId:    str
    recordType:    RecordType
    title:         str
    content:       str                  # plaintext — will be encrypted
    accessPolicy:  list[str]            = Field(default_factory=list)
    tags:          list[str]            = Field(default_factory=list)
    recordDate:    Optional[str]        = None


# ---------------------------------------------------------------------------
# Database model
# ---------------------------------------------------------------------------

class EHRRecordInDB(BaseModel):
    """
    Document stored in MongoDB.

    AES-GCM fields:
      encryptedContent — base64-encoded ciphertext
      iv               — base64-encoded 12-byte initialisation vector
                         (fresh random bytes per record — NEVER reused)
      The GCM authentication tag is appended to encryptedContent by
      the cryptography library; see crypto/aes.py for handling details.

    ⚠ HARDCODE WARNING: The encryption key is derived from
    `settings.demo_encryption_password` via PBKDF2.  In production,
    use a per-record DEK (Data Encryption Key) wrapped with a KMS
    (Key Management Service) master key.
    """
    id:               str
    patientId:        str
    hospitalId:       str
    createdBy:        str                 # user id of the creating doctor
    recordType:       RecordType
    title:            str
    encryptedContent: str                 # base64 AES-256-GCM ciphertext
    iv:               str                 # base64 12-byte IV
    accessPolicy:     list[str]           = Field(default_factory=list)
    tags:             list[str]           = Field(default_factory=list)
    createdAt:        str
    updatedAt:        str
    isFlagged:        bool                = False
    status:           str                 = "approved"


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

class RecordResponse(BaseModel):
    """
    Returned to API clients.

    `decryptedContent` is populated only when the requesting user's
    attributes satisfy the record's `accessPolicy` (CP-ABE check).
    Otherwise it is None and the client receives only metadata.
    """
    id:               str
    patientId:        str
    hospitalId:       str
    createdBy:        str
    recordType:       RecordType
    title:            str
    encryptedContent: str
    iv:               str
    accessPolicy:     list[str]
    tags:             list[str]
    createdAt:        str
    updatedAt:        str
    isFlagged:        bool
    status:           str                 = "approved"
    decryptedContent: Optional[str]       = None  # None if access denied
