"""
dependencies.py — Reusable FastAPI dependency functions.

These are injected into route handlers via Depends().

Key dependencies:
  get_current_user  → decodes the JWT bearer token, returns UserInDB
  role_required     → factory that raises 403 if user's role isn't in allowed list
  get_simulated_ip  → returns a fake IP for audit logs (replace with real IP in prod)

Usage:
    from dependencies import get_current_user, role_required

    # Any authenticated route:
    @router.get("/patients/{id}")
    async def get_patient(user: UserInDB = Depends(get_current_user)):
        ...

    # Role-protected route:
    @router.get("/users", dependencies=[Depends(role_required("admin"))])
    async def list_users():
        ...

    # Multi-role:
    @router.post("/records", dependencies=[Depends(role_required("doctor", "admin"))])
    async def create_record():
        ...
"""

import random
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorDatabase

from config import settings
from database import REVOCATION_LIST, USERS, get_database
from models.user import UserInDB

# ---------------------------------------------------------------------------
# OAuth2 scheme — FastAPI reads the Bearer token from the Authorization header
# tokenUrl must match the actual login endpoint so Swagger UI's "Authorize"
# button works correctly.
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ---------------------------------------------------------------------------
# Current user dependency
# ---------------------------------------------------------------------------

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> UserInDB:
    """
    Decode the JWT and return the authenticated user document from MongoDB.

    FastAPI automatically extracts the token from:
        Authorization: Bearer <token>

    Raises:
        401 UNAUTHORIZED — token is missing, malformed, or expired
        403 FORBIDDEN    — user account has been revoked

    Returns:
        UserInDB — the full user document (including passwordHash, privateKey).
        Route handlers should return UserResponse (without those fields) to clients.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Check revocation list first (faster than a full user lookup in some cases)
    revoked = await db[REVOCATION_LIST].find_one({"userId": user_id})
    if revoked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account access has been revoked. Contact your administrator.",
        )

    # Fetch full user document
    user_doc = await db[USERS].find_one({"id": user_id})
    if user_doc is None:
        raise credentials_exception

    # Double-check the isRevoked flag on the user document itself
    if user_doc.get("isRevoked", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account access has been revoked. Contact your administrator.",
        )

    # Remove MongoDB's _id before constructing the model
    user_doc.pop("_id", None)
    return UserInDB(**user_doc)


# ---------------------------------------------------------------------------
# Role guard factory
# ---------------------------------------------------------------------------

def role_required(*roles: str) -> Callable:
    """
    Dependency factory — raises 403 if the current user's role is not
    in the allowed list.

    Usage:
        # Single role:
        dependencies=[Depends(role_required("admin"))]

        # Multiple roles:
        dependencies=[Depends(role_required("doctor", "admin"))]

    Args:
        *roles: One or more role strings from UserRole enum.

    Returns:
        An async dependency function compatible with FastAPI's Depends().
    """
    async def _check(user: UserInDB = Depends(get_current_user)) -> UserInDB:
        if user.role.value not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied — required role: {' or '.join(roles)}",
            )
        return user

    return _check


# ---------------------------------------------------------------------------
# Simulated IP (for audit logs)
# ---------------------------------------------------------------------------

def get_simulated_ip() -> str:
    """
    Return a simulated IP address for audit log entries.

    ⚠ HARDCODE WARNING: This generates a fake RFC-1918 IP for demo purposes.
    In production, read the real client IP from the request:
        from fastapi import Request
        ip = request.client.host
    Or, if behind a proxy/load balancer:
        ip = request.headers.get("X-Forwarded-For", request.client.host)
    """
    # HARDCODE: random private-range IP — replace with real IP extraction in production
    return f"192.168.{random.randint(1, 5)}.{random.randint(10, 200)}"
