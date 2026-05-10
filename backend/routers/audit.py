"""
routers/audit.py — Audit trail read and chain verification endpoints.

Routes:
  GET /audit        — paginated audit log (newest first), admin only
  GET /audit/verify — verify entire hash chain integrity, admin only
"""

import math
from typing import Optional

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from crypto.hashing import compute_audit_hash
from database import AUDIT_LOGS, get_database
from dependencies import get_current_user, role_required
from models.audit import AccessLogResponse
from models.user import UserInDB

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get(
    "",
    summary="Paginated audit log",
    dependencies=[Depends(role_required("admin", "patient"))],
)
async def list_audit_logs(
    action:      Optional[str] = Query(None),
    user_id:     Optional[str] = Query(None),
    hospital_id: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    date_from:   Optional[str] = Query(None),
    date_to:     Optional[str] = Query(None),
    page:        int           = Query(1, ge=1),
    limit:       int           = Query(20, ge=1, le=100),
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    """Return paginated audit entries, newest first. All filters are optional."""
    query: dict = {}
    if action:
        query["action"] = action
    if user_id:
        query["userId"] = user_id
    if hospital_id:
        query["hospitalId"] = hospital_id
    if resource_id:
        query["resourceId"] = resource_id
    if date_from or date_to:
        query["timestamp"] = {}
        if date_from:
            query["timestamp"]["$gte"] = date_from
        if date_to:
            query["timestamp"]["$lte"] = date_to

    skip  = (page - 1) * limit
    docs  = await db[AUDIT_LOGS].find(query).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
    total = await db[AUDIT_LOGS].count_documents(query)

    logs = []
    for doc in docs:
        doc.pop("_id", None)
        logs.append(AccessLogResponse(**doc).model_dump())

    return {
        "logs":  logs,
        "total": total,
        "page":  page,
        "pages": math.ceil(total / limit) if limit else 1,
    }


@router.get(
    "/verify",
    summary="Verify audit log hash chain integrity (admin only)",
    dependencies=[Depends(role_required("admin"))],
)
async def verify_audit_chain(
    current_user: UserInDB             = Depends(get_current_user),
    db:           AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    """
    Walk ALL audit entries in chronological order and verify every hash.

    For each entry, recomputes:
        compute_audit_hash(entry.prevHash,
            f"{userId}{action}{resourceType}{resourceId}{timestamp}{details}")
    and compares to the stored hash.

    Returns intact=True only if every entry matches.
    brokenAt contains the ID of the first tampered/missing entry.

    ⚠ HARDCODE WARNING: Loads all logs into memory.
    Add pagination for large datasets in production.
    """
    all_docs = await db[AUDIT_LOGS].find().sort("timestamp", 1).to_list(None)

    total = len(all_docs)
    verified = 0
    failed   = 0
    broken_at: Optional[str] = None

    for doc in all_docs:
        doc.pop("_id", None)
        entry = AccessLogResponse(**doc)

        entry_data = (
            f"{entry.userId}"
            f"{entry.action.value}"
            f"{entry.resourceType.value}"
            f"{entry.resourceId}"
            f"{entry.timestamp}"
            f"{entry.details}"
        )

        expected = compute_audit_hash(entry.prevHash, entry_data)

        if expected == entry.hash:
            verified += 1
        else:
            failed += 1
            if broken_at is None:
                broken_at = entry.id

    return {
        "total":    total,
        "verified": verified,
        "failed":   failed,
        "intact":   failed == 0,
        "brokenAt": broken_at,
    }
