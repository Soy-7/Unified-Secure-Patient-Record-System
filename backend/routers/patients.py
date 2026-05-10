"""
routers/patients.py — Patient CRUD + phonetic search endpoints.

Routes:
  GET  /patients          — paginated list + optional fuzzy (Soundex) search
  POST /patients          — create new patient (doctor/admin only)
  GET  /patients/{id}     — patient detail
  PUT  /patients/{id}     — update patient info (doctor/admin only)

Search logic:
  If `search` query param is provided, the search runs two passes:
    1. Soundex match — compute soundex(search), compare to soundexCode index
    2. Name regex — case-insensitive contains match on the name field
  Results from either match are returned, and each result has a
  `phoneticMatch: true` field if the soundex index was the reason it matched.

Audit:
  CREATE → AuditAction.CREATE
  VIEW   → AuditAction.VIEW
  UPDATE → AuditAction.UPDATE
"""

import math
import re
import uuid
import random
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from crypto.soundex import soundex
from database import PATIENTS, get_database
from dependencies import get_current_user, get_simulated_ip, role_required
from models.audit import AuditAction, AuditResourceType
from models.patient import PatientCreate, PatientInDB, PatientResponse
from models.user import UserInDB
from utils.audit_writer import write_audit_log

router = APIRouter(prefix="/patients", tags=["Patients"])


# ---------------------------------------------------------------------------
# GET /patients — list + search
# ---------------------------------------------------------------------------

@router.get(
    "",
    summary="List patients with optional phonetic search",
)
async def list_patients(
    search:      Optional[str] = Query(None, description="Name search (exact + Soundex)"),
    hospital_id: Optional[str] = Query(None, description="Filter by hospital"),
    page:        int           = Query(1,    ge=1),
    limit:       int           = Query(10,   ge=1, le=100),
    current_user: UserInDB       = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    """
    Return a paginated list of patients.

    If `search` is provided:
    - Soundex code of the query is matched against the `soundexCode` field (indexed)
    - A case-insensitive regex is also run on the `name` field
    - Results include `phoneticMatch: true` when the Soundex matched
    """
    query: dict = {}

    # Hospital filter: match either as primary or linked hospital
    if hospital_id:
        query["$or"] = [
            {"primaryHospitalId": hospital_id},
            {"linkedHospitalIds": hospital_id},
        ]

    skip = (page - 1) * limit

    if search:
        search_code = soundex(search)
        # Regex for partial name match (case-insensitive)
        name_pattern = re.compile(re.escape(search), re.IGNORECASE)

        # Build combined $or — soundex OR name regex OR exact ID match
        search_conditions: list[dict] = [
            {"id": search},
            {"soundexCode": search_code},
            {"name": {"$regex": name_pattern}},
        ]

        if "$or" in query:
            # Merge with existing hospital filter using $and
            query = {"$and": [query, {"$or": search_conditions}]}
        else:
            query["$or"] = search_conditions

        docs  = await db[PATIENTS].find(query).skip(skip).limit(limit).to_list(limit)
        total = await db[PATIENTS].count_documents(query)

        # Tag each result with whether the Soundex index was the match reason
        patients_out = []
        for doc in docs:
            doc.pop("_id", None)
            p = PatientResponse(**doc)
            phonetic = p.soundexCode == search_code
            patients_out.append({**p.model_dump(), "phoneticMatch": phonetic})

    else:
        docs  = await db[PATIENTS].find(query).skip(skip).limit(limit).to_list(limit)
        total = await db[PATIENTS].count_documents(query)

        patients_out = []
        for doc in docs:
            doc.pop("_id", None)
            p = PatientResponse(**doc)
            patients_out.append({**p.model_dump(), "phoneticMatch": False})

    return {
        "patients": patients_out,
        "total":    total,
        "page":     page,
        "pages":    math.ceil(total / limit) if limit else 1,
    }


# ---------------------------------------------------------------------------
# POST /patients — create
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new patient",
    dependencies=[Depends(role_required("admin"))],
)
async def create_patient(
    body:         PatientCreate,
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> PatientResponse:
    """
    Create a new patient record.

    Soundex code is computed from the patient's name and stored as
    `soundexCode` for fast phonetic search queries.
    """
    now = datetime.now(timezone.utc).isoformat()
    
    # Generate unique 10-digit patient ID
    while True:
        patient_id = "".join([str(random.randint(0, 9)) for _ in range(10)])
        existing = await db[PATIENTS].find_one({"id": patient_id})
        if not existing:
            break

    patient = PatientInDB(
        id=patient_id,
        soundexCode=soundex(body.name),
        name=body.name,
        dob=body.dob,
        gender=body.gender,
        bloodGroup=body.bloodGroup,
        phone=body.phone,
        email=body.email,
        address=body.address,
        primaryHospitalId=body.primaryHospitalId,
        linkedHospitalIds=[],
        emergencyContact=body.emergencyContact,
        createdAt=now,
        updatedAt=now,
    )

    await db[PATIENTS].insert_one(patient.model_dump())

    await write_audit_log(
        db=db,
        user=current_user,
        action=AuditAction.CREATE,
        resource_type=AuditResourceType.patient,
        resource_id=patient_id,
        hospital_id=current_user.hospitalId,
        ip_address=get_simulated_ip(),
        details=f"Created patient '{body.name}'",
    )

    return PatientResponse(**patient.model_dump())


# ---------------------------------------------------------------------------
# GET /patients/{id} — detail
# ---------------------------------------------------------------------------

@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Get patient detail",
)
async def get_patient(
    patient_id:   str,
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> PatientResponse:
    """Fetch a single patient by ID. Audit-logged as a VIEW action."""
    doc = await db[PATIENTS].find_one({"id": patient_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    doc.pop("_id", None)

    await write_audit_log(
        db=db,
        user=current_user,
        action=AuditAction.VIEW,
        resource_type=AuditResourceType.patient,
        resource_id=patient_id,
        hospital_id=current_user.hospitalId,
        ip_address=get_simulated_ip(),
        details=f"Viewed patient '{doc.get('name', patient_id)}'",
    )

    return PatientResponse(**doc)


# ---------------------------------------------------------------------------
# PUT /patients/{id} — update
# ---------------------------------------------------------------------------

@router.put(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Update patient info",
    dependencies=[Depends(role_required("doctor", "admin"))],
)
async def update_patient(
    patient_id:   str,
    body:         dict,
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> PatientResponse:
    """
    Update allowed patient fields.

    Only the fields present in the request body are updated.
    `id`, `soundexCode`, `createdAt` cannot be changed.
    If `name` is updated, `soundexCode` is recomputed automatically.
    `updatedAt` is always set to the current time.
    """
    doc = await db[PATIENTS].find_one({"id": patient_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    # Fields that cannot be changed by a PUT
    immutable = {"id", "_id", "soundexCode", "createdAt"}
    updates = {k: v for k, v in body.items() if k not in immutable}

    # If the name changed, recompute soundexCode
    if "name" in updates:
        updates["soundexCode"] = soundex(updates["name"])

    updates["updatedAt"] = datetime.now(timezone.utc).isoformat()

    await db[PATIENTS].update_one({"id": patient_id}, {"$set": updates})

    updated_doc = await db[PATIENTS].find_one({"id": patient_id})
    updated_doc.pop("_id", None)

    await write_audit_log(
        db=db,
        user=current_user,
        action=AuditAction.UPDATE,
        resource_type=AuditResourceType.patient,
        resource_id=patient_id,
        hospital_id=current_user.hospitalId,
        ip_address=get_simulated_ip(),
        details=f"Updated patient '{updated_doc.get('name', patient_id)}'",
    )

    return PatientResponse(**updated_doc)
