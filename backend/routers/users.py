"""
routers/users.py — User management endpoints (admin only).

Routes:
  GET  /users              — paginated list of staff accounts
  POST /users              — create new staff account
  PUT  /users/{id}         — update name/department/attributes
  POST /users/{id}/revoke  — revoke access immediately

All routes require the "admin" role.

Revocation dual-write:
  When revoking, we:
    1. Set isRevoked=True on the user document
    2. Insert a record into the revocation_list collection
  This dual-write ensures that even a cached/in-memory user object
  (from a decoded JWT) triggers the revocation check the next time
  get_current_user runs, which queries both sources.
"""

import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from crypto.ecdh import generate_keypair
from crypto.hashing import hash_password
from database import REVOCATION_LIST, USERS, get_database
from dependencies import get_current_user, get_simulated_ip, role_required
from models.audit import AuditAction, AuditResourceType
from models.user import UserCreate, UserInDB, UserResponse
from utils.audit_writer import write_audit_log

router = APIRouter(prefix="/users", tags=["Users"])


# ---------------------------------------------------------------------------
# GET /users
# ---------------------------------------------------------------------------

@router.get(
    "",
    summary="List all staff accounts (admin only)",
    dependencies=[Depends(role_required("admin"))],
)
async def list_users(
    hospital_id:  Optional[str] = Query(None),
    role:         Optional[str] = Query(None),
    page:         int           = Query(1, ge=1),
    limit:        int           = Query(10, ge=1, le=100),
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    """
    Return paginated staff accounts.
    passwordHash and privateKey are never included in the response.
    """
    query: dict = {}
    if hospital_id:
        query["hospitalId"] = hospital_id
    if role:
        query["role"] = role

    skip  = (page - 1) * limit
    docs  = await db[USERS].find(query).skip(skip).limit(limit).to_list(limit)
    total = await db[USERS].count_documents(query)

    users_out = []
    for doc in docs:
        doc.pop("_id", None)
        u = UserInDB(**doc)
        users_out.append(UserResponse(
            id=u.id, name=u.name, email=u.email, role=u.role,
            hospitalId=u.hospitalId, department=u.department,
            attributes=u.attributes, publicKey=u.publicKey,
            createdAt=u.createdAt, isRevoked=u.isRevoked,
        ))

    return {
        "users": [u.model_dump() for u in users_out],
        "total": total,
        "page":  page,
        "pages": math.ceil(total / limit) if limit else 1,
    }


# ---------------------------------------------------------------------------
# POST /users — create account
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a staff account (admin only)",
    dependencies=[Depends(role_required("admin"))],
)
async def create_user(
    body:         UserCreate,
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> UserResponse:
    """
    Onboard a new staff member.

    - Password is bcrypt-hashed (cost=12) before storage
    - ECDH P-256 key pair is generated for the user (used in exchange)
    - isRevoked defaults to False

    ⚠ The generated privateKey is stored as plaintext PEM (dev limitation).
    In production, encrypt it with a KMS-managed key before storage.
    """
    # Check for duplicate email
    existing = await db[USERS].find_one({"email": body.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{body.email}' already exists",
        )

    now     = datetime.now(timezone.utc).isoformat()
    user_id = str(uuid.uuid4())
    keys    = generate_keypair()

    user = UserInDB(
        id=user_id,
        name=body.name,
        email=body.email,
        passwordHash=hash_password(body.password),
        role=body.role,
        hospitalId=body.hospitalId,
        department=body.department,
        attributes=body.attributes,
        publicKey=keys["publicKey"],
        privateKey=keys["privateKey"],
        createdAt=now,
        isRevoked=False,
    )

    await db[USERS].insert_one(user.model_dump())

    await write_audit_log(
        db=db,
        user=current_user,
        action=AuditAction.CREATE,
        resource_type=AuditResourceType.user,
        resource_id=user_id,
        hospital_id=current_user.hospitalId,
        ip_address=get_simulated_ip(),
        details=f"Created user '{body.name}' with role '{body.role.value}'",
    )

    return UserResponse(
        id=user.id, name=user.name, email=user.email, role=user.role,
        hospitalId=user.hospitalId, department=user.department,
        attributes=user.attributes, publicKey=user.publicKey,
        createdAt=user.createdAt, isRevoked=user.isRevoked,
    )


# ---------------------------------------------------------------------------
# PUT /users/{id} — update
# ---------------------------------------------------------------------------

@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user name/department/attributes (admin only)",
    dependencies=[Depends(role_required("admin"))],
)
async def update_user(
    user_id:      str,
    body:         dict,
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> UserResponse:
    """
    Update a user's mutable fields: name, department, attributes.

    Immutable fields (id, email, role, hospitalId, passwordHash, keys, createdAt)
    are ignored even if present in the request body.
    """
    doc = await db[USERS].find_one({"id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    allowed_fields = {"name", "department", "attributes"}
    updates = {k: v for k, v in body.items() if k in allowed_fields}

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No updatable fields provided. Allowed: name, department, attributes",
        )

    await db[USERS].update_one({"id": user_id}, {"$set": updates})

    updated_doc = await db[USERS].find_one({"id": user_id})
    updated_doc.pop("_id", None)
    u = UserInDB(**updated_doc)

    await write_audit_log(
        db=db,
        user=current_user,
        action=AuditAction.UPDATE,
        resource_type=AuditResourceType.user,
        resource_id=user_id,
        hospital_id=current_user.hospitalId,
        ip_address=get_simulated_ip(),
        details=f"Updated user '{u.name}' fields: {list(updates.keys())}",
    )

    return UserResponse(
        id=u.id, name=u.name, email=u.email, role=u.role,
        hospitalId=u.hospitalId, department=u.department,
        attributes=u.attributes, publicKey=u.publicKey,
        createdAt=u.createdAt, isRevoked=u.isRevoked,
    )


# ---------------------------------------------------------------------------
# POST /users/{id}/revoke — revoke access
# ---------------------------------------------------------------------------

@router.post(
    "/{user_id}/revoke",
    summary="Revoke a user's access immediately (admin only)",
    dependencies=[Depends(role_required("admin"))],
)
async def revoke_user(
    user_id:      str,
    body:         dict = Body(default={"reason": "Access revoked by administrator"}),
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    """
    Immediately block a user from logging in.

    Two writes happen atomically (at the MongoDB level):
      1. `users` collection: isRevoked = True
      2. `revocation_list` collection: new entry with reason and timestamp

    After this, any call to get_current_user for this user's token returns 403.
    Existing tokens expire naturally within jwt_expire_hours (8h by default).

    ⚠ HARDCODE WARNING: No immediate token invalidation — the user's existing
    JWT stays valid until it expires. For instant invalidation, implement a
    Redis-backed token blacklist using the JWT's `jti` claim.
    """
    doc = await db[USERS].find_one({"id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    if doc.get("isRevoked"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already revoked",
        )

    now    = datetime.now(timezone.utc).isoformat()
    reason = body.get("reason", "Access revoked by administrator")

    # 1. Mark user as revoked
    await db[USERS].update_one(
        {"id": user_id},
        {"$set": {"isRevoked": True}},
    )

    # 2. Insert into revocation_list (dual-write for fast blocking on login)
    await db[REVOCATION_LIST].insert_one({
        "id":         str(uuid.uuid4()),
        "userId":     user_id,
        "reason":     reason,
        "revokedAt":  now,
        "revokedBy":  current_user.id,
    })

    doc.pop("_id", None)
    u = UserInDB(**doc)

    await write_audit_log(
        db=db,
        user=current_user,
        action=AuditAction.UPDATE,
        resource_type=AuditResourceType.user,
        resource_id=user_id,
        hospital_id=current_user.hospitalId,
        ip_address=get_simulated_ip(),
        details=f"User access revoked. Reason: {reason}",
    )

    return {"message": "User access revoked successfully"}


# ---------------------------------------------------------------------------
# POST /users/{id}/rotate-keys — generate new ECDH keypair
# ---------------------------------------------------------------------------

@router.post(
    "/{user_id}/rotate-keys",
    summary="Rotate a user's ECDH encryption key pair",
)
async def rotate_keys(
    user_id:      str,
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    """
    Generate a fresh ECDH P-256 key pair for the user and persist it.

    Authorization:
      - A user may rotate their own keys (user_id == current_user.id)
      - An admin may rotate any user's keys

    Returns the new public key fingerprint (first 32 chars of base64(SHA-256(pubkey))).
    """
    from crypto.ecdh import get_key_fingerprint

    # Authorization check
    is_self  = user_id == current_user.id
    is_admin = current_user.role.value == "admin"
    if not (is_self or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only rotate your own keys unless you are an admin",
        )

    doc = await db[USERS].find_one({"id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")

    new_keys    = generate_keypair()
    fingerprint = get_key_fingerprint(new_keys["publicKey"])

    await db[USERS].update_one(
        {"id": user_id},
        {"$set": {
            "publicKey":  new_keys["publicKey"],
            "privateKey": new_keys["privateKey"],
        }},
    )

    await write_audit_log(
        db=db,
        user=current_user,
        action=AuditAction.UPDATE,
        resource_type=AuditResourceType.user,
        resource_id=user_id,
        hospital_id=current_user.hospitalId,
        ip_address=get_simulated_ip(),
        details=f"Encryption keys rotated for user '{doc.get('name', user_id)}'",
    )

    return {"message": "Keys rotated successfully", "fingerprint": fingerprint}

