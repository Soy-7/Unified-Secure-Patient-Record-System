"""
routers/records.py — Encrypted medical record endpoints.

Routes:
  GET  /records          — paginated list (metadata only, no decryption)
  POST /records          — create + AES-256-GCM encrypt (doctor/admin)
  GET  /records/{id}     — CP-ABE access check + decrypt if authorised
  PUT  /records/{id}/flag — toggle isFlagged (doctor/admin)

Encryption scheme:
  - Key = PBKDF2-HMAC-SHA256(demo_encryption_password, STATIC_SALT)
  - IV  = os.urandom(12) — fresh per record (never reused!)
  - Ciphertext stored as: base64(ciphertext_bytes + tag_bytes)
    The 16-byte GCM authentication tag is appended to ciphertext before
    base64 encoding, so only two DB fields are needed: encryptedContent + iv.

  On decrypt: split last 16 bytes from decoded encryptedContent as tag,
  pass both to AESGCM for authenticated decryption.

CP-ABE access:
  can_access(user.attributes, record.accessPolicy)
  → all(attr in user.attributes for attr in record.accessPolicy)
  → Empty policy ([]) grants access to everyone (intentional).

⚠ HARDCODE WARNING: STATIC_SALT b"EHR-SALT-2024-STATIC" is used for all
records. In production, use a unique salt per record (stored alongside iv)
and a KMS-managed master key, not the demo password.
"""

import base64
import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from config import settings
from crypto.aes import decrypt as aes_decrypt
from crypto.aes import derive_key_from_password
from crypto.aes import encrypt as aes_encrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from database import RECORDS, get_database
from dependencies import get_current_user, get_simulated_ip, role_required
from models.audit import AuditAction, AuditResourceType
from models.record import EHRRecordInDB, RecordCreate, RecordResponse
from models.user import UserInDB
from utils.audit_writer import write_audit_log

router = APIRouter(prefix="/records", tags=["Records"])

# ---------------------------------------------------------------------------
# Encryption key setup
# HARDCODE: static salt shared across all records — replace with per-record
#           salt + KMS in production.
# ---------------------------------------------------------------------------
_STATIC_SALT = b"EHR-SALT-2024-STATIC"  # HARDCODE — see module docstring


def _get_demo_key() -> bytes:
    """Derive the AES-256 encryption key from the demo password + static salt."""
    return derive_key_from_password(settings.demo_encryption_password, _STATIC_SALT)


# ---------------------------------------------------------------------------
# CP-ABE access check
# ---------------------------------------------------------------------------

def can_access(user_attributes: list[str], record_policy: list[str]) -> bool:
    """
    Simplified CP-ABE policy evaluation.

    Returns True if user_attributes satisfies ALL attributes in record_policy.
    An empty policy ([]) grants access to everyone.

    This check MUST happen server-side — never trust the frontend to enforce it.

    Args:
        user_attributes: List of attribute strings from the user's JWT/DB record.
                         e.g. ["doctor", "hospital-001", "oncology"]
        record_policy:   List of required attributes for this record.
                         e.g. ["doctor", "hospital-001"]

    Returns:
        True if user_attributes contains ALL items in record_policy.
    """
    return all(attr in user_attributes for attr in record_policy)


# ---------------------------------------------------------------------------
# GET /records — paginated list
# ---------------------------------------------------------------------------

@router.get(
    "",
    summary="List records (metadata only, no decryption)",
)
async def list_records(
    patient_id:   Optional[str] = Query(None),
    hospital_id:  Optional[str] = Query(None),
    record_type:  Optional[str] = Query(None),
    page:         int           = Query(1, ge=1),
    limit:        int           = Query(10, ge=1, le=100),
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    """
    Return paginated record metadata. Content is NOT decrypted in list view
    — clients must call GET /records/{id} individually for decrypted data.

    Filtered to the current user's hospital by default.
    """
    query: dict = {"hospitalId": current_user.hospitalId}

    if patient_id:
        query["patientId"] = patient_id
    if hospital_id:
        query["hospitalId"] = hospital_id  # allow override for admins
    if record_type:
        query["recordType"] = record_type

    skip  = (page - 1) * limit
    docs  = await db[RECORDS].find(query).skip(skip).limit(limit).to_list(limit)
    total = await db[RECORDS].count_documents(query)

    records_out = []
    for doc in docs:
        doc.pop("_id", None)
        records_out.append(EHRRecordInDB(**doc).model_dump())

    return {
        "records": records_out,
        "total":   total,
        "page":    page,
        "pages":   math.ceil(total / limit) if limit else 1,
    }


# ---------------------------------------------------------------------------
# POST /records — create + encrypt
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=EHRRecordInDB,
    status_code=status.HTTP_201_CREATED,
    summary="Create and encrypt a medical record",
    dependencies=[Depends(role_required("doctor", "admin", "nurse", "patient"))],
)
async def create_record(
    body:         RecordCreate,
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> EHRRecordInDB:
    """
    Encrypt and store a medical record.

    The plaintext `content` field is AES-256-GCM encrypted before storage.
    The encryptedContent DB field stores base64(ciphertext + tag) combined,
    and iv is stored separately. This way only 2 fields are needed for decryption.
    """
    # If patient, they can only create records for themselves
    if current_user.role == "patient":
        # Look up patient doc by email or exact name
        patient_doc = await db["patients"].find_one({"$or": [{"email": current_user.email}, {"name": current_user.name}]})
        if not patient_doc or patient_doc["id"] != body.patientId:
            print(f"DEBUG POST /records 403: user.email={current_user.email}, user.name={current_user.name}")
            print(f"DEBUG patient_doc={patient_doc}, body.patientId={body.patientId}")
            raise HTTPException(status_code=403, detail="Patients can only upload documents to their own timeline.")
            
    # Workflow: Doctors create 'pending' records for hospital approval. Patients create 'approved' personal documents? 
    # Or doctors send to hospital to approve. Let's make doctor creations 'pending', and hospital creations 'approved'.
    status_val = "pending" if current_user.role == "doctor" else "approved"

    key = _get_demo_key()

    # Encrypt — aes_encrypt returns {"ciphertext", "iv", "tag"} all as base64
    enc = aes_encrypt(body.content, key)

    # Combine ciphertext + tag into one base64 blob for storage
    ct_bytes  = base64.b64decode(enc["ciphertext"])
    tag_bytes = base64.b64decode(enc["tag"])
    encrypted_content = base64.b64encode(ct_bytes + tag_bytes).decode("utf-8")

    # Use provided recordDate or default to current time
    now       = body.recordDate if body.recordDate else datetime.now(timezone.utc).isoformat()
    record_id = str(uuid.uuid4())

    record = EHRRecordInDB(
        id=record_id,
        patientId=body.patientId,
        hospitalId=body.hospitalId,
        createdBy=current_user.id,
        recordType=body.recordType,
        title=body.title,
        encryptedContent=encrypted_content,
        iv=enc["iv"],
        accessPolicy=body.accessPolicy,
        tags=body.tags,
        createdAt=now,
        updatedAt=now,
        isFlagged=False,
        status=status_val,
    )

    await db[RECORDS].insert_one(record.model_dump())

    await write_audit_log(
        db=db,
        user=current_user,
        action=AuditAction.CREATE,
        resource_type=AuditResourceType.record,
        resource_id=record_id,
        hospital_id=current_user.hospitalId,
        ip_address=get_simulated_ip(),
        details=f"Created {body.recordType.value} record '{body.title}' for patient {body.patientId}",
    )

    return record


# ---------------------------------------------------------------------------
# GET /records/{id} — CP-ABE check + decrypt
# ---------------------------------------------------------------------------

@router.get(
    "/{record_id}",
    response_model=RecordResponse,
    summary="Get record detail with CP-ABE check and decryption",
)
async def get_record(
    record_id:    str,
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> RecordResponse:
    """
    Fetch, policy-check, and decrypt a single record.

    CP-ABE check:
      - Server evaluates: all(attr in user.attributes for attr in record.accessPolicy)
      - If the check fails → 403 with a detailed message (and ACCESS_DENIED audit log)
      - If it passes → decrypt content → return with decryptedContent populated

    The 403 body intentionally reveals which attributes are missing so the
    user knows whether to request consent or contact their admin.
    """
    doc = await db[RECORDS].find_one({"id": record_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    doc.pop("_id", None)
    record = EHRRecordInDB(**doc)

    # -----------------------------------------------------------------------
    # CP-ABE Policy & Consent check (server-side — frontend cannot bypass this)
    # -----------------------------------------------------------------------
    is_owner = False
    if current_user.role == "patient":
        patient_doc = await db["patients"].find_one({"$or": [{"email": current_user.email}, {"name": current_user.name}]})
        if patient_doc and patient_doc["id"] == record.patientId:
            is_owner = True

    is_creator = (current_user.id == record.createdBy)
    
    # Check for active consent
    has_consent = False
    if not is_owner and not is_creator:
        now_str = datetime.now(timezone.utc).isoformat()
        consent_query = {
            "patientId": record.patientId,
            "isRevoked": False,
            "grantedTo": {"$in": [current_user.id, current_user.hospitalId]},
            "validFrom": {"$lte": now_str},
            "validUntil": {"$gte": now_str},
            "permissions": "read"
        }
        if await db["consents"].find_one(consent_query):
            has_consent = True

    # Final access decision:
    # Patient can always access their own records.
    # Creator can always access records they created.
    # Others need BOTH (CP-ABE attributes matching) AND (Explicit Consent).
    has_attributes = can_access(current_user.attributes, record.accessPolicy)
    
    can_view = is_owner or is_creator or (has_attributes and has_consent)

    if not can_view:
        await write_audit_log(
            db=db,
            user=current_user,
            action=AuditAction.ACCESS_DENIED,
            resource_type=AuditResourceType.record,
            resource_id=record_id,
            hospital_id=current_user.hospitalId,
            ip_address=get_simulated_ip(),
            details=(
                f"Access denied to record '{record.title}'. "
                f"User attributes {current_user.attributes} did not satisfy "
                f"policy {record.accessPolicy} or no consent was found."
            ),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "detail":           "Access Denied",
                "message":          (
                    "Access requires explicit patient consent or you must be the creator of this record. "
                    f"Your attributes {current_user.attributes} may also be insufficient for policy {record.accessPolicy}."
                ),
                "userAttributes":   current_user.attributes,
                "requiredPolicy":   record.accessPolicy,
            },
        )

    # -----------------------------------------------------------------------
    # Decrypt content
    # encryptedContent = base64(ciphertext + tag), iv stored separately
    # -----------------------------------------------------------------------
    key = _get_demo_key()
    try:
        ct_and_tag = base64.b64decode(record.encryptedContent)
        ct_b64     = base64.b64encode(ct_and_tag[:-16]).decode("utf-8")
        tag_b64    = base64.b64encode(ct_and_tag[-16:]).decode("utf-8")
        plaintext  = aes_decrypt(ct_b64, record.iv, tag_b64, key)
    except Exception as exc:
        # If decryption fails (bad tag, corrupted data) — don't expose details
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Decryption failed — record may be corrupted or key has changed",
        ) from exc

    await write_audit_log(
        db=db,
        user=current_user,
        action=AuditAction.VIEW,
        resource_type=AuditResourceType.record,
        resource_id=record_id,
        hospital_id=current_user.hospitalId,
        ip_address=get_simulated_ip(),
        details=f"Viewed and decrypted record '{record.title}'",
    )

    return RecordResponse(
        **record.model_dump(),
        decryptedContent=plaintext,
    )


# ---------------------------------------------------------------------------
# PUT /records/{id}/flag — toggle flag
# ---------------------------------------------------------------------------

@router.put(
    "/{record_id}/flag",
    response_model=EHRRecordInDB,
    summary="Toggle isFlagged on a record (doctor/admin)",
    dependencies=[Depends(role_required("doctor", "admin"))],
)
async def flag_record(
    record_id:    str,
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> EHRRecordInDB:
    """
    Toggle the `isFlagged` field on a record.

    Flagged records appear highlighted in the UI as requiring attention
    (e.g. unusual lab values, potential data quality issues).
    """
    doc = await db[RECORDS].find_one({"id": record_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    new_flag  = not doc.get("isFlagged", False)
    now       = datetime.now(timezone.utc).isoformat()

    await db[RECORDS].update_one(
        {"id": record_id},
        {"$set": {"isFlagged": new_flag, "updatedAt": now}},
    )

    updated_doc = await db[RECORDS].find_one({"id": record_id})
    updated_doc.pop("_id", None)

    flag_label = "flagged" if new_flag else "unflagged"
    await write_audit_log(
        db=db,
        user=current_user,
        action=AuditAction.UPDATE,
        resource_type=AuditResourceType.record,
        resource_id=record_id,
        hospital_id=current_user.hospitalId,
        ip_address=get_simulated_ip(),
        details=f"Record '{updated_doc.get('title', record_id)}' {flag_label}",
    )

    return EHRRecordInDB(**updated_doc)


# ---------------------------------------------------------------------------
# PUT /records/{id}/status — toggle status
# ---------------------------------------------------------------------------

@router.put(
    "/{record_id}/status",
    response_model=EHRRecordInDB,
    summary="Update record status (nurse/admin)",
    dependencies=[Depends(role_required("nurse", "admin"))],
)
async def update_record_status(
    record_id:    str,
    status_val:   str                  = Query(..., description="'approved' or 'rejected'"),
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> EHRRecordInDB:
    """Approve or reject a pending record draft from a doctor."""
    doc = await db[RECORDS].find_one({"id": record_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    now = datetime.now(timezone.utc).isoformat()
    await db[RECORDS].update_one(
        {"id": record_id},
        {"$set": {"status": status_val, "updatedAt": now}},
    )

    updated_doc = await db[RECORDS].find_one({"id": record_id})
    updated_doc.pop("_id", None)

    await write_audit_log(
        db=db,
        user=current_user,
        action=AuditAction.UPDATE,
        resource_type=AuditResourceType.record,
        resource_id=record_id,
        hospital_id=current_user.hospitalId,
        ip_address=get_simulated_ip(),
        details=f"Record '{updated_doc.get('title', record_id)}' status changed to {status_val}",
    )
    return EHRRecordInDB(**updated_doc)
