"""
routers/auth.py — Authentication endpoints.

Routes:
  POST /auth/login   — verify credentials, issue JWT, write audit log
  POST /auth/logout  — write logout audit log, confirm to client

Security flow (login):
  1. Look up user by email
  2. Check RevocationList (separate collection) — 403 if found
  3. verify_password(plain, hash) — bcrypt check
  4. Generate JWT with: sub, email, role, hospital_id, attributes, exp
  5. Write LOGIN audit log entry (chained hash)
  6. Return TokenResponse

Why two revocation checks?
  RevocationList is checked here (fast collection scan on login).
  get_current_user in dependencies.py checks it again on every request.
  This dual check ensures revoked users are blocked immediately even if
  they have a valid in-flight token from before revocation.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from motor.motor_asyncio import AsyncIOMotorDatabase

from config import settings
from crypto.hashing import verify_password
from database import REVOCATION_LIST, USERS, get_database
from dependencies import get_current_user, get_simulated_ip
from models.audit import AuditAction, AuditResourceType
from models.user import TokenResponse, UserInDB, UserResponse
from utils.audit_writer import write_audit_log

import uuid

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive a JWT",
    responses={
        401: {"description": "Invalid credentials"},
        403: {"description": "Account revoked"},
    },
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> TokenResponse:
    """
    Authenticate a user and return a JWT access token.

    Uses OAuth2PasswordRequestForm so the Swagger UI "Authorize" button works.
    The form sends `username` (mapped to email here) and `password`.

    Process:
      1. Look up user by email (form_data.username)
      2. Check RevocationList — 403 if present
      3. verify_password — 401 if mismatch
      4. Sign JWT with user claims
      5. Write LOGIN audit entry
      6. Return TokenResponse
    """
    # 1. Find user by email
    user_doc = await db[USERS].find_one({"email": form_data.username})
    if not user_doc:
        # Deliberately vague error — don't reveal whether the email exists
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access denied — credentials not recognised",
        )

    user_doc.pop("_id", None)
    user = UserInDB(**user_doc)

    # 2. Check RevocationList (separate collection for fast blocking)
    revoked = await db[REVOCATION_LIST].find_one({"userId": user.id})
    if revoked or user.isRevoked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account access has been revoked. Contact your administrator.",
        )

    # 3. Verify password (bcrypt — constant-time comparison)
    if not verify_password(form_data.password, user.passwordHash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access denied — credentials not recognised",
        )

    # 4. Build JWT payload
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub":         user.id,
        "email":       user.email,
        "role":        user.role.value,
        "hospital_id": user.hospitalId,
        "attributes":  user.attributes,
        "exp":         expire,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    # 5. Write audit log
    ip = get_simulated_ip()
    await write_audit_log(
        db=db,
        user=user,
        action=AuditAction.LOGIN,
        resource_type=AuditResourceType.system,
        resource_id="system",
        hospital_id=user.hospitalId,
        ip_address=ip,
        details=f"User '{user.name}' ({user.role.value}) logged in",
    )

    # 6. Return token + safe user representation
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            hospitalId=user.hospitalId,
            department=user.department,
            attributes=user.attributes,
            publicKey=user.publicKey,
            createdAt=user.createdAt,
            isRevoked=user.isRevoked,
        ),
    )


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

@router.post(
    "/logout",
    summary="Logout and record the session end",
    responses={
        401: {"description": "Not authenticated"},
    },
)
async def logout(
    user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    """
    Record a logout event in the audit trail.

    The JWT itself is NOT invalidated server-side (stateless JWT design).
    The client is responsible for discarding the token from memory (Zustand store).

    ⚠ HARDCODE WARNING: No server-side token blacklist is implemented.
    In production, add the token's `jti` (JWT ID) claim and maintain a
    Redis blacklist that's checked in get_current_user.  TTL = token expiry.
    """
    ip = get_simulated_ip()
    await write_audit_log(
        db=db,
        user=user,
        action=AuditAction.LOGOUT,
        resource_type=AuditResourceType.system,
        resource_id="system",
        hospital_id=user.hospitalId,
        ip_address=ip,
        details=f"User '{user.name}' ({user.role.value}) logged out",
    )

    return {"message": "Logged out successfully"}
