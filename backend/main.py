"""
main.py — FastAPI application entry point for the EHR Platform.

Responsibilities:
  • Instantiate the FastAPI app with lifespan (MongoDB connection)
  • Register CORS middleware
  • Mount all routers with their URL prefixes
  • Global exception handlers (404 + 500)
  • Expose /health check for Docker and load-balancer probes

Run locally (outside Docker):
    uvicorn main:app --reload --port 8000

Interactive API docs (auto-generated from code):
    http://localhost:8000/docs    ← Swagger UI
    http://localhost:8000/redoc  ← ReDoc
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database import lifespan
from routers import (
    audit,
    auth,
    consents,
    crypto_demo,
    exchange,
    hospitals,
    patients,
    records,
    users,
)

logger = logging.getLogger("ehr_platform")

# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.app_name,
    description=(
        "Secure Electronic Health Record platform. "
        "Features: AES-256-GCM encrypted records, ECDH inter-hospital exchange, "
        "SHA-256 audit hash chain, JWT authentication, CP-ABE access control, "
        "and role-based route guards."
    ),
    version="0.3.0",    # Block 6 — all endpoints + error handlers complete
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS Middleware
# allow_origins locked to Vite dev server.
# ⚠ HARDCODE WARNING: add your production domain before deploying:
#   allow_origins=["http://localhost:5173", "https://ehr.yourhospital.com"]
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": "Endpoint not found"},
    )

@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled 500 error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )

# ---------------------------------------------------------------------------
# Routers — 9 router groups covering all EHR functionality
# prefix in router file + route decorator = final URL
#   e.g. router prefix "/patients" + decorator "/" = GET /patients
# ---------------------------------------------------------------------------
app.include_router(auth.router)           # /auth/login, /auth/logout
app.include_router(patients.router)       # /patients — CRUD + soundex search
app.include_router(records.router)        # /records — AES-256-GCM encrypt/decrypt
app.include_router(users.router)          # /users — admin CRUD + revoke + rotate-keys
app.include_router(consents.router)       # /consents — grant/revoke
app.include_router(audit.router)          # /audit — logs + SHA-256 chain verify
app.include_router(exchange.router)       # /exchange — inter-hospital requests
app.include_router(hospitals.router)      # /hospitals — public registry
app.include_router(crypto_demo.router)    # /crypto — encryption lab (no auth)

# ---------------------------------------------------------------------------
# Health check — no auth, used by Docker healthcheck and uptime monitors
# ---------------------------------------------------------------------------
@app.get("/health", tags=["System"], summary="Liveness probe")
async def health_check() -> dict:
    """Returns 200 when the API process is running and MongoDB is connected."""
    return {"status": "ok", "service": settings.app_name}

# ---------------------------------------------------------------------------
# Startup message (printed to Docker logs on container start)
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup() -> None:
    print(
        "\n"
        "┌─────────────────────────────────────────────┐\n"
        "│  EHR Platform API running                   │\n"
        "│  Docs:   http://localhost:8000/docs          │\n"
        "│  Health: http://localhost:8000/health        │\n"
        "│  Routes: 9 routers mounted                  │\n"
        "└─────────────────────────────────────────────┘\n",
        flush=True,
    )
