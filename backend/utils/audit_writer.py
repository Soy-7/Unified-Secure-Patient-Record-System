"""
utils/audit_writer.py — Centralised audit log writer used by all routers.

Every router that performs a write action (CREATE, UPDATE, DELETE, SHARE,
VIEW of sensitive data, ACCESS_DENIED) imports and calls write_audit_log().
Having one place ensures:
  • The hash chain is computed consistently everywhere
  • No router can accidentally skip audit logging
  • Future changes to the log format only need to happen here

Hash chain:
  Each entry stores prevHash (the previous entry's hash) and its own hash.
  entry_data = f"{userId}{action}{resourceType}{resourceId}{timestamp}{details}"
  current_hash = SHA-256(prevHash + entry_data)

Genesis hash:
  The very first log entry ever written uses AUDIT_GENESIS_HASH as prevHash.
  This is "0" * 64 — 64 zero characters, a conventional chain start marker.
"""

import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from crypto.hashing import AUDIT_GENESIS_HASH, compute_audit_hash
from database import AUDIT_LOGS
from models.audit import AccessLogInDB, AuditAction, AuditResourceType
from models.user import UserInDB


async def write_audit_log(
    db: AsyncIOMotorDatabase,
    user: UserInDB,
    action: AuditAction,
    resource_type: AuditResourceType,
    resource_id: str,
    hospital_id: str,
    ip_address: str,
    details: str = "",
) -> None:
    """
    Append one entry to the audit log hash chain.

    Args:
        db:            Active Motor database handle (from Depends(get_database)).
        user:          The authenticated user performing the action.
        action:        What was done (AuditAction enum value).
        resource_type: Category of the resource (AuditResourceType enum value).
        resource_id:   The specific resource's ID. Use "system" for auth events.
        hospital_id:   The hospital context (usually current_user.hospitalId).
        ip_address:    Client IP address (real or simulated in dev).
        details:       Optional human-readable description of the action.

    Example usage in a router:
        from utils.audit_writer import write_audit_log
        from models.audit import AuditAction, AuditResourceType
        from dependencies import get_simulated_ip

        await write_audit_log(
            db=db,
            user=current_user,
            action=AuditAction.CREATE,
            resource_type=AuditResourceType.patient,
            resource_id=new_patient.id,
            hospital_id=current_user.hospitalId,
            ip_address=get_simulated_ip(),
            details=f"Created patient '{new_patient.name}'",
        )
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Fetch the most recent audit entry to continue the chain
    # Sort descending on timestamp — newest entry = last in chain
    last_entry = await db[AUDIT_LOGS].find_one(
        sort=[("timestamp", -1)]
    )
    prev_hash = last_entry["hash"] if last_entry else AUDIT_GENESIS_HASH

    # Build the entry data string (must be identical between write and verify)
    # Format is: userId + action + resourceType + resourceId + timestamp + details
    # (all concatenated, no separator — changing this breaks existing chains)
    entry_data = (
        f"{user.id}"
        f"{action.value}"
        f"{resource_type.value}"
        f"{resource_id}"
        f"{timestamp}"
        f"{details}"
    )

    entry_hash = compute_audit_hash(prev_hash, entry_data)

    log_entry = AccessLogInDB(
        id=str(uuid.uuid4()),
        userId=user.id,
        userName=user.name,
        userRole=user.role.value,
        action=action,
        resourceType=resource_type,
        resourceId=resource_id,
        hospitalId=hospital_id,
        ipAddress=ip_address,
        timestamp=timestamp,
        hash=entry_hash,
        prevHash=prev_hash,
        details=details,
    )

    await db[AUDIT_LOGS].insert_one(log_entry.model_dump())
