"""
database.py — Async MongoDB connection and collection constants.

Uses the Motor async driver so FastAPI can handle thousands of concurrent
requests without blocking on DB calls.

Pattern:
  - One Motor client per application lifetime (stored in module-level vars)
  - FastAPI lifespan() opens the connection on startup, closes it on shutdown
  - get_database() is used as a FastAPI dependency in route handlers

Collection name constants:
  All collection names are defined here as string constants.
  Import from this module — never hardcode collection names in routers.

Usage in a router:
    from database import get_database, PATIENTS

    @router.get("/patients")
    async def list_patients(db = Depends(get_database)):
        docs = await db[PATIENTS].find().to_list(100)
        return docs
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from config import settings

# ---------------------------------------------------------------------------
# Collection name constants
# Change these strings if you rename collections in MongoDB.
# ---------------------------------------------------------------------------
USERS             = "users"
PATIENTS          = "patients"
RECORDS           = "records"
AUDIT_LOGS        = "audit_logs"
CONSENTS          = "consents"
HOSPITALS         = "hospitals"
EXCHANGE_REQUESTS = "exchange_requests"
REVOCATION_LIST   = "revocation_list"

# ---------------------------------------------------------------------------
# Module-level client references (set during lifespan startup)
# ---------------------------------------------------------------------------
_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None   = None


@asynccontextmanager
async def lifespan(app):  # noqa: ANN001 — avoids circular import with FastAPI type
    """
    FastAPI lifespan context manager.

    Wires the Motor client to the application lifetime:
      - Opens the connection and pings MongoDB on startup
      - Closes the connection cleanly on shutdown

    Wire it to FastAPI in main.py:
        from database import lifespan
        app = FastAPI(..., lifespan=lifespan)
    """
    global _client, _db

    _client = AsyncIOMotorClient(settings.mongodb_url)
    _db     = _client.get_default_database()

    # Fail fast — if MongoDB isn't reachable, crash now with a clear error
    # rather than on the first real request.
    await _client.admin.command("ping")
    print(f"[DB] ✓ Connected to MongoDB  →  {settings.mongodb_url}")

    yield  # Application handles requests here

    _client.close()
    print("[DB] MongoDB connection closed")


async def get_database() -> AsyncIOMotorDatabase:
    """
    FastAPI dependency — inject the active database into route handlers.

    Example:
        @router.get("/")
        async def handler(db = Depends(get_database)):
            result = await db[USERS].find_one(...)

    Raises:
        RuntimeError: if called before the lifespan has started
                      (e.g. during import-time code — don't do that).
    """
    if _db is None:
        raise RuntimeError(
            "Database not initialised. "
            "Ensure `lifespan` from database.py is passed to FastAPI()."
        )
    return _db
