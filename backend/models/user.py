"""
models/user.py — User account Pydantic schemas.

Three model tiers (standard FastAPI pattern):
  UserCreate   → what the API accepts as input
  UserInDB     → what's stored in MongoDB (includes sensitive fields)
  UserResponse → what's returned to clients (sensitive fields stripped)
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    """Allowed roles in the system. Determines which routes a user can access."""
    admin   = "admin"
    doctor  = "doctor"
    nurse   = "nurse"
    patient = "patient"


# ---------------------------------------------------------------------------
# Input model (API → Backend)
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    """
    Schema for creating a new user account.
    Sent by the admin when onboarding a new staff member.

    `attributes` is a list of CP-ABE style strings, e.g.:
      ["doctor", "hospital-001", "oncology"]
    Used by the access-policy check in records.
    """
    name:        str
    email:       EmailStr
    password:    str
    role:        UserRole
    hospitalId:  str
    department:  Optional[str]        = None
    attributes:  list[str]            = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Database model (Backend → MongoDB)
# ---------------------------------------------------------------------------

class UserInDB(BaseModel):
    """
    Full user document as stored in MongoDB.

    Key security fields:
      passwordHash — bcrypt hash (never the plaintext password)
      publicKey    — ECDH P-256 key in PEM format (safe to share)
      privateKey   — ECDH P-256 key in PEM format
                     ⚠ HARDCODE WARNING: stored as plaintext PEM here.
                     In production, encrypt with a per-user KEK (Key Encryption Key)
                     or store in a hardware security module (HSM).
      isRevoked    — if True, the user cannot log in even with a valid password.
    """
    id:           str
    name:         str
    email:        str
    passwordHash: str                 # bcrypt — never expose this in responses
    role:         UserRole
    hospitalId:   str
    department:   Optional[str]       = None
    attributes:   list[str]           = Field(default_factory=list)
    publicKey:    str                 # ECDH P-256 PEM (despite the "JWK" label in spec)
    privateKey:   str                 # ECDH P-256 PEM — see HARDCODE WARNING above
    createdAt:    str                 # ISO-8601 datetime string
    isRevoked:    bool                = False


# ---------------------------------------------------------------------------
# Response model (Backend → API client)
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    """
    Safe user representation returned to API clients.
    passwordHash and privateKey are intentionally excluded.
    """
    id:           str
    name:         str
    email:        str
    role:         UserRole
    hospitalId:   str
    department:   Optional[str]       = None
    attributes:   list[str]           = Field(default_factory=list)
    publicKey:    str
    createdAt:    str
    isRevoked:    bool


# ---------------------------------------------------------------------------
# Token response (returned by POST /auth/login)
# ---------------------------------------------------------------------------

class TokenResponse(BaseModel):
    """
    JWT auth token + user info returned on successful login.
    The frontend should store `access_token` in memory (Zustand)
    — NOT in localStorage (vulnerable to XSS).
    """
    access_token: str
    token_type:   str       = "bearer"
    user:         UserResponse
