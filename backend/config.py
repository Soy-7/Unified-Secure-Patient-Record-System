"""
config.py — Application settings loaded from environment variables.

All values are read from the environment (injected by Docker Compose) or
fall back to the defaults defined here.  For local dev without Docker,
create a backend/.env file — pydantic-settings reads it automatically.

Example backend/.env:
    MONGODB_URL=mongodb://localhost:27017/ehrdb
    JWT_SECRET=my-local-dev-secret
    JWT_EXPIRE_HOURS=8
    DEMO_ENCRYPTION_PASSWORD=EHR-DEMO-KEY-2024
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # MongoDB
    # Injected by Docker Compose as: MONGODB_URL=mongodb://mongodb:27017/ehrdb
    # ⚠ HARDCODE WARNING: The default points to localhost for running outside Docker.
    # ------------------------------------------------------------------
    mongodb_url: str = "mongodb://localhost:27017/ehrdb"

    # ------------------------------------------------------------------
    # JWT Authentication
    # ⚠ HARDCODE WARNING: jwt_secret has a weak default for local dev ONLY.
    # Before any real deployment, set JWT_SECRET env var to a 32-byte random hex:
    #   python -c "import secrets; print(secrets.token_hex(32))"
    # ------------------------------------------------------------------
    jwt_secret: str      = "change-me-before-any-real-deployment"
    jwt_algorithm: str   = "HS256"   # HARDCODE: change to RS256 for prod (asymmetric)
    jwt_expire_hours: int = 8

    # ------------------------------------------------------------------
    # Application metadata
    # ------------------------------------------------------------------
    app_name: str = "EHR Platform"
    debug: bool   = False

    # ------------------------------------------------------------------
    # Demo encryption master password
    # Used by crypto/aes.py to derive the AES key for encrypting records.
    # ⚠ HARDCODE WARNING: This is a single master password for ALL records.
    # In production, replace with a proper KMS (AWS KMS, HashiCorp Vault, etc.)
    # and use a unique DEK per record, wrapped by the KMS master key.
    # ------------------------------------------------------------------
    demo_encryption_password: str = "EHR-DEMO-KEY-2024"  # HARDCODE: change before prod

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# ---------------------------------------------------------------------------
# Module-level singleton — import `settings` everywhere.
# Never instantiate Settings() directly in other modules.
# ---------------------------------------------------------------------------
settings = Settings()
