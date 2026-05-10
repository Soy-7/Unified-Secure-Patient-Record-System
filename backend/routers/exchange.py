"""
routers/exchange.py — Inter-hospital record exchange endpoints.

Routes:
  GET /exchange              — list requests involving current user's hospital
  POST /exchange             — create new exchange request
  PUT /exchange/{id}/approve — approve and simulate encrypted payload transfer
  PUT /exchange/{id}/reject  — reject a request

Approve flow (simulated):
  1. Fetch all records of requested types for the patient
  2. Serialize them to JSON
  3. Encrypt with AES-256-GCM (same demo key)
  4. Store as encryptedPayload on the request
  5. Set status = completed

In production this would use ECDH-derived per-exchange keys (see crypto/ecdh.py),
where the requestor's ephemeral public key is sent with the request and the
target hospital derives a unique shared secret for each transfer.
"""

import base64
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from config import settings
from crypto.aes import derive_key_from_password
from crypto.aes import encrypt as aes_encrypt
from database import EXCHANGE_REQUESTS, RECORDS, get_database
from dependencies import get_current_user, get_simulated_ip, role_required
from models.audit import AuditAction, AuditResourceType
from models.exchange import (
    ExchangeRequestCreate,
    ExchangeRequestInDB,
    ExchangeRequestResponse,
    ExchangeStatus,
)
from models.user import UserInDB
from utils.audit_writer import write_audit_log

router = APIRouter(prefix="/exchange", tags=["Exchange"])

_STATIC_SALT = b"EHR-SALT-2024-STATIC"  # HARDCODE — same as records.py


def _get_demo_key() -> bytes:
    return derive_key_from_password(settings.demo_encryption_password, _STATIC_SALT)


# ---------------------------------------------------------------------------
# GET /exchange
# ---------------------------------------------------------------------------

@router.get("", summary="List exchange requests for current hospital")
async def list_exchange_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> list[ExchangeRequestResponse]:
    """Return requests where this hospital is either the sender or receiver."""
    query: dict = {
        "$or": [
            {"fromHospitalId": current_user.hospitalId},
            {"toHospitalId":   current_user.hospitalId},
        ]
    }
    if status_filter:
        query["status"] = status_filter

    docs = await db[EXCHANGE_REQUESTS].find(query).to_list(None)
    result = []
    for doc in docs:
        doc.pop("_id", None)
        result.append(ExchangeRequestResponse(**doc))
    return result


# ---------------------------------------------------------------------------
# POST /exchange — create request
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ExchangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an inter-hospital record request",
    dependencies=[Depends(role_required("doctor", "admin"))],
)
async def create_exchange_request(
    body:         ExchangeRequestCreate,
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> ExchangeRequestResponse:
    """Submit a request to another hospital for patient records."""
    now        = datetime.now(timezone.utc).isoformat()
    request_id = str(uuid.uuid4())

    req = ExchangeRequestInDB(
        id=request_id,
        fromHospitalId=current_user.hospitalId,
        toHospitalId=body.toHospitalId,
        patientId=body.patientId,
        requestedBy=current_user.id,
        status=ExchangeStatus.pending,
        recordTypes=body.recordTypes,
        purpose=body.purpose,
        encryptedPayload=None,
        createdAt=now,
        resolvedAt=None,
    )

    await db[EXCHANGE_REQUESTS].insert_one(req.model_dump())

    await write_audit_log(
        db=db, user=current_user,
        action=AuditAction.SHARE,
        resource_type=AuditResourceType.hospital,
        resource_id=body.toHospitalId,
        hospital_id=current_user.hospitalId,
        ip_address=get_simulated_ip(),
        details=f"Exchange request to hospital {body.toHospitalId} for patient {body.patientId}",
    )

    return ExchangeRequestResponse(**req.model_dump())


# ---------------------------------------------------------------------------
# PUT /exchange/{id}/approve
# ---------------------------------------------------------------------------

@router.put(
    "/{request_id}/approve",
    response_model=ExchangeRequestResponse,
    summary="Approve exchange request and transfer encrypted payload",
    dependencies=[Depends(role_required("doctor", "admin"))],
)
async def approve_exchange_request(
    request_id:   str,
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> ExchangeRequestResponse:
    """
    Approve an exchange request.

    Simulated transfer:
    1. Fetch all records of requested types for the patient
    2. Build a JSON summary (metadata only — no decryption needed for transfer)
    3. AES-encrypt the JSON with the demo key
    4. Store as encryptedPayload; set status = completed

    Production note: use derive_shared_secret(target_private_key, requestor_public_key)
    from crypto/ecdh.py to derive a unique key per exchange instead of the demo key.
    """
    doc = await db[EXCHANGE_REQUESTS].find_one({"id": request_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    doc.pop("_id", None)
    req = ExchangeRequestInDB(**doc)

    if req.status != ExchangeStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request is already '{req.status.value}' — cannot approve",
        )

    # Fetch the relevant records for this patient + requested types
    record_query: dict = {"patientId": req.patientId}
    if req.recordTypes:
        record_query["recordType"] = {"$in": req.recordTypes}

    record_docs = await db[RECORDS].find(record_query).to_list(None)
    for r in record_docs:
        r.pop("_id", None)

    # Build a safe summary (metadata only — encryptedContent stays encrypted)
    summary = [
        {
            "id": r.get("id"), "recordType": r.get("recordType"),
            "title": r.get("title"), "createdAt": r.get("createdAt"),
            "tags": r.get("tags", []),
            # encryptedContent is included as-is — the receiving hospital
            # would use ECDH-derived key to re-decrypt in production
            "encryptedContent": r.get("encryptedContent"),
            "iv": r.get("iv"),
        }
        for r in record_docs
    ]

    # Encrypt the summary JSON with demo key
    key = _get_demo_key()
    enc = aes_encrypt(json.dumps(summary), key)
    ct_bytes  = base64.b64decode(enc["ciphertext"])
    tag_bytes = base64.b64decode(enc["tag"])
    encrypted_payload = base64.b64encode(ct_bytes + tag_bytes).decode("utf-8") + "|" + enc["iv"]

    now = datetime.now(timezone.utc).isoformat()
    await db[EXCHANGE_REQUESTS].update_one(
        {"id": request_id},
        {"$set": {
            "status":           ExchangeStatus.completed.value,
            "encryptedPayload": encrypted_payload,
            "resolvedAt":       now,
        }},
    )

    updated = await db[EXCHANGE_REQUESTS].find_one({"id": request_id})
    updated.pop("_id", None)

    await write_audit_log(
        db=db, user=current_user,
        action=AuditAction.SHARE,
        resource_type=AuditResourceType.record,
        resource_id=req.patientId,
        hospital_id=current_user.hospitalId,
        ip_address=get_simulated_ip(),
        details=f"Approved exchange {request_id}: transferred {len(record_docs)} records",
    )

    return ExchangeRequestResponse(**updated)


# ---------------------------------------------------------------------------
# PUT /exchange/{id}/reject
# ---------------------------------------------------------------------------

@router.put(
    "/{request_id}/reject",
    response_model=ExchangeRequestResponse,
    summary="Reject an exchange request",
    dependencies=[Depends(role_required("doctor", "admin"))],
)
async def reject_exchange_request(
    request_id:   str,
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> ExchangeRequestResponse:
    """Reject a pending exchange request."""
    doc = await db[EXCHANGE_REQUESTS].find_one({"id": request_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    doc.pop("_id", None)
    req = ExchangeRequestInDB(**doc)

    if req.status != ExchangeStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request is already '{req.status.value}'",
        )

    now = datetime.now(timezone.utc).isoformat()
    await db[EXCHANGE_REQUESTS].update_one(
        {"id": request_id},
        {"$set": {"status": ExchangeStatus.rejected.value, "resolvedAt": now}},
    )

    updated = await db[EXCHANGE_REQUESTS].find_one({"id": request_id})
    updated.pop("_id", None)

    await write_audit_log(
        db=db, user=current_user,
        action=AuditAction.UPDATE,
        resource_type=AuditResourceType.hospital,
        resource_id=req.fromHospitalId,
        hospital_id=current_user.hospitalId,
        ip_address=get_simulated_ip(),
        details=f"Rejected exchange request {request_id}",
    )

    return ExchangeRequestResponse(**updated)
