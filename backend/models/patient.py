"""
models/patient.py — Patient record Pydantic schemas.
"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------

class PatientCreate(BaseModel):
    """
    Submitted when registering a new patient (intake / receptionist flow).

    `emergencyContact` is a free-form dict, e.g.:
      {"name": "Jane Doe", "relation": "spouse", "phone": "+91-9999999999"}
    """
    name:               str
    dob:                str                   # ISO date string  e.g. "1985-03-22"
    gender:             str                   # "male" | "female" | "other"
    bloodGroup:         str                   # e.g. "O+", "AB-"
    phone:              str
    email:              Optional[EmailStr]    = None
    address:            str
    primaryHospitalId:  str
    emergencyContact:   dict                  = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Database model
# ---------------------------------------------------------------------------

class PatientInDB(BaseModel):
    """
    Full patient document stored in MongoDB.

    `soundexCode` — pre-computed at creation time using crypto/soundex.py.
    Indexed in MongoDB. Allows fuzzy phonetic name search without scanning
    all documents on every query.

    `linkedHospitalIds` — grows as the patient is treated at more hospitals.
    Populated during inter-hospital exchange approvals.
    """
    id:                 str
    soundexCode:        str                   # e.g. "S600" for "Srihari"
    name:               str
    dob:                str
    gender:             str
    bloodGroup:         str
    phone:              str
    email:              Optional[str]         = None
    address:            str
    primaryHospitalId:  str
    linkedHospitalIds:  list[str]             = Field(default_factory=list)
    emergencyContact:   dict                  = Field(default_factory=dict)
    createdAt:          str
    updatedAt:          str


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

class PatientResponse(BaseModel):
    """Returned to API clients — same as PatientInDB (no sensitive-only fields)."""
    id:                 str
    soundexCode:        str
    name:               str
    dob:                str
    gender:             str
    bloodGroup:         str
    phone:              str
    email:              Optional[str]         = None
    address:            str
    primaryHospitalId:  str
    linkedHospitalIds:  list[str]
    emergencyContact:   dict
    createdAt:          str
    updatedAt:          str
