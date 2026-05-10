"""
routers/consents.py — Patient consent management endpoints.

Routes:
  GET    /consents/patient/{patient_id} — list consents for a patient
  POST   /consents                      — grant consent (doctor/admin)
  DELETE /consents/{id}                 — revoke consent (doctor/admin)

Consent defines which users or hospitals can access which of a patient's
records, for what actions (read/write/share), and for how long.

Access note:
  Nurses and patients can only query consents for patients in their own
  hospital. Admins and doctors can query any patient's consents.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import CONSENTS, get_database
from dependencies import get_current_user, get_simulated_ip, role_required
from models.audit import AuditAction, AuditResourceType
from models.consent import ConsentCreate, ConsentInDB, ConsentResponse
from models.user import UserInDB
from utils.audit_writer import write_audit_log

router = APIRouter(prefix="/consents", tags=["Consents"])


# ---------------------------------------------------------------------------
# GET /consents/patient/{patient_id}
# ---------------------------------------------------------------------------

@router.get(
    "/patient/{patient_id}",
    response_model=list[ConsentResponse],
    summary="List all consents for a patient",
)
async def list_patient_consents(
    patient_id:   str,
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> list[ConsentResponse]:
    """
    Return all consent records for a given patient.

    Role-based filtering:
    - admin / doctor → can query any patient's consents
    - nurse / patient → only if the consent's hospitalId matches their own hospital
      (approximated by checking the grantedTo field or the requesting user's hospital)
    """
    query: dict = {"patientId": patient_id}

    # Nurses and patient role: restrict to their own hospital's context
    # (Admins and doctors can see all consents for the patient)
    restricted_roles = {"nurse", "patient"}
    if current_user.role.value in restricted_roles:
        # Only return consents where grantedTo is within this hospital
        query["grantedTo"] = current_user.hospitalId

    docs = await db[CONSENTS].find(query).to_list(None)
    consents = []
    for doc in docs:
        doc.pop("_id", None)
        consents.append(ConsentResponse(**doc))
    return consents


# ---------------------------------------------------------------------------
# POST /consents — grant
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ConsentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Grant consent for a patient's records",
    dependencies=[Depends(role_required("doctor", "admin"))],
)
async def grant_consent(
    body:         ConsentCreate,
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> ConsentResponse:
    """
    Grant a user or hospital access to one or more of a patient's records.

    `recordIds = ["*"]` grants access to all current and future records.
    Consent is time-bounded by `validFrom` and `validUntil` — both ISO-8601.
    """
    now        = datetime.now(timezone.utc).isoformat()
    consent_id = str(uuid.uuid4())

    consent = ConsentInDB(
        id=consent_id,
        patientId=body.patientId,
        grantedTo=body.grantedTo,
        grantedToType=body.grantedToType,
        recordIds=body.recordIds,
        permissions=body.permissions,
        validFrom=body.validFrom,
        validUntil=body.validUntil,
        isRevoked=False,
        revokedAt=None,
        createdAt=now,
    )

    await db[CONSENTS].insert_one(consent.model_dump())

    await write_audit_log(
        db=db,
        user=current_user,
        action=AuditAction.SHARE,
        resource_type=AuditResourceType.patient,
        resource_id=body.patientId,
        hospital_id=current_user.hospitalId,
        ip_address=get_simulated_ip(),
        details=(
            f"Consent granted to '{body.grantedTo}' ({body.grantedToType}) "
            f"for patient {body.patientId}. "
            f"Permissions: {body.permissions}. "
            f"Valid: {body.validFrom} → {body.validUntil}"
        ),
    )

    return ConsentResponse(**consent.model_dump())


# ---------------------------------------------------------------------------
# DELETE /consents/{id} — revoke
# ---------------------------------------------------------------------------

@router.delete(
    "/{consent_id}",
    summary="Revoke a consent grant",
    dependencies=[Depends(role_required("doctor", "admin"))],
)
async def revoke_consent(
    consent_id:   str,
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    """
    Soft-delete a consent grant by setting isRevoked=True and revokedAt=now.

    The record is NOT deleted from MongoDB — we preserve it for the audit trail.
    Any check for active consent should filter by isRevoked=False.
    """
    doc = await db[CONSENTS].find_one({"id": consent_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    if doc.get("isRevoked"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Consent is already revoked",
        )

    now = datetime.now(timezone.utc).isoformat()
    await db[CONSENTS].update_one(
        {"id": consent_id},
        {"$set": {"isRevoked": True, "revokedAt": now}},
    )

    await write_audit_log(
        db=db,
        user=current_user,
        action=AuditAction.UPDATE,
        resource_type=AuditResourceType.patient,
        resource_id=doc.get("patientId", consent_id),
        hospital_id=current_user.hospitalId,
        ip_address=get_simulated_ip(),
        details=f"Consent {consent_id} revoked",
    )

    return {"message": "Consent revoked"}
