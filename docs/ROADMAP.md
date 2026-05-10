# Project Roadmap

Tracks what's done, what's being built, and what's planned.
Update this file at the end of every phase.

---

## Phase 1 — Infrastructure Scaffold ✅ COMPLETE

**Goal:** Get everything running. No business logic yet.

### What was built:
- [x] `docker-compose.yml` — 3 services (MongoDB, Backend, Frontend) with healthcheck
- [x] `backend/Dockerfile` — Python 3.11-slim, uvicorn with live reload
- [x] `backend/requirements.txt` — all pinned dependencies
- [x] `backend/main.py` — FastAPI app, CORS, router mounts, `/health` endpoint
- [x] `backend/config.py` — pydantic-settings reads env vars (MONGODB_URL, JWT_SECRET, etc.)
- [x] `backend/database.py` — Motor async client, lifespan management, `get_database()` dependency
- [x] `backend/dependencies.py` — placeholder for `get_current_user`, `role_required`
- [x] `backend/seed.py` — async scaffold, ready to be filled
- [x] 9 router files — each with correct prefix, tags, and docstring
- [x] 7 model files — each with field plan in docstring
- [x] 4 crypto files — each with API contract in docstring
- [x] `frontend/Dockerfile` — Node 20 Alpine, non-root user
- [x] `frontend/package.json` — all deps with compatible versions
- [x] `frontend/vite.config.ts` — `/api` proxy to backend
- [x] `frontend/tailwind.config.js` — brand color palette, Inter font
- [x] `frontend/postcss.config.js` — required by Tailwind v3
- [x] `frontend/tsconfig.json` — strict TypeScript
- [x] `frontend/index.html` — Vite entry point
- [x] `frontend/src/main.tsx` — React 18 createRoot + StrictMode
- [x] `frontend/src/App.tsx` — scaffold landing page ("EHR Platform — Running")
- [x] `frontend/src/index.css` — Tailwind directives + dark base theme

### Verification:
- [x] `docker compose up --build` succeeds
- [x] `http://localhost:8000/health` → `{"status":"ok"}`
- [x] `http://localhost:5173` → landing page renders

### Documentation created:
- [x] `README.md` — project overview and quick start
- [x] `docs/ARCHITECTURE.md` — system design + flow diagrams
- [x] `docs/BACKEND.md` — backend code walkthrough
- [x] `docs/FRONTEND.md` — frontend code walkthrough
- [x] `docs/SECURITY.md` — all 7 security pillars explained
- [x] `docs/DEVELOPMENT.md` — setup, commands, conventions, troubleshooting
- [x] `docs/API_REFERENCE.md` — all endpoints documented
- [x] `docs/ROADMAP.md` — this file

---

## Phase 2 — Authentication & Data Models ✅ COMPLETE

**Goal:** A real user can log in and get a JWT. The DB schema is locked down.

### Backend tasks completed:
- [x] `models/user.py` — UserRole enum, UserCreate, UserInDB, UserResponse, TokenResponse
- [x] `models/patient.py` — PatientCreate, PatientInDB, PatientResponse (with soundexCode)
- [x] `models/record.py` — RecordType enum, RecordCreate, EHRRecordInDB, RecordResponse (decryptedContent optional)
- [x] `models/audit.py` — AuditAction + AuditResourceType enums, AccessLogInDB/Response with hash chain fields
- [x] `models/consent.py` — ConsentCreate, ConsentInDB, ConsentResponse
- [x] `models/hospital.py` — HospitalInDB, HospitalResponse
- [x] `models/exchange.py` — ExchangeStatus enum, ExchangeRequestCreate, InDB, Response
- [x] `crypto/hashing.py` — bcrypt (cost 12), verify_password, sha256_hex, compute_audit_hash, AUDIT_GENESIS_HASH
- [x] `crypto/ecdh.py` — generate_keypair (P-256 PEM), derive_shared_secret (HKDF), get_key_fingerprint
- [x] `crypto/aes.py` — derive_key_from_password (PBKDF2), encrypt (fresh IV), decrypt (tag split)
- [x] `crypto/soundex.py` — full Soundex algorithm + soundex_search helper
- [x] `config.py` — demo_encryption_password field added, all HARDCODE warnings documented
- [x] `database.py` — 8 collection constants (USERS, PATIENTS, RECORDS, AUDIT_LOGS, CONSENTS, HOSPITALS, EXCHANGE_REQUESTS, REVOCATION_LIST)
- [x] `dependencies.py` — get_current_user (JWT decode + dual revocation check), role_required factory, get_simulated_ip
- [x] `routers/auth.py` — POST /auth/login (OAuth2 form, dual revocation, bcrypt, JWT, audit log), POST /auth/logout
- [x] `main.py` — updated to v0.2.0, all 9 routers mounted with prefix comments

### Frontend tasks:
- [ ] `src/store/authStore.ts` — Zustand store (token, user, login, logout)
- [ ] `src/api/client.ts` — Axios instance + JWT interceptor + 401 handler
- [ ] `src/pages/Login.tsx` — email/password form, calls `/auth/login`
- [ ] Protected route wrapper in `App.tsx`

### Verification:
- [ ] `docker compose up --build` succeeds with Phase 2 code
- [ ] POST /auth/login returns 401 for wrong creds, 403 for revoked accounts
- [ ] Audit log entry written on login
- [ ] run `python seed.py` to create test users (seed.py to be implemented)

### HARDCODE items introduced in this phase:
| Item | File | What to change for production |
|---|---|---|
| `demo_encryption_password` default | `config.py` | Use KMS (AWS KMS, Vault) per-record DEK |
| PBKDF2 iterations = 100,000 | `crypto/aes.py` | Increase to 600,000+ for production |
| bcrypt rounds = 12 | `crypto/hashing.py` | Increase to 13-14 on stronger servers |
| HKDF salt = None (static) | `crypto/ecdh.py` | Use session-specific nonce as salt |
| Simulated IP address | `dependencies.py` | Read `request.headers["X-Forwarded-For"]` |
| No JWT blacklist on logout | `routers/auth.py` | Add Redis `jti` blacklist with TTL = token expiry |
| CORS origin = localhost only | `main.py` | Add production domain |
| JWT algorithm = HS256 | `config.py` | Use RS256 (asymmetric) for multi-service prod |

---

## Phase 3 — Core Feature Routers ✅ COMPLETE

**Goal:** All backend routes fully implemented.

### Backend tasks completed:
- [x] `utils/audit_writer.py` — shared write_audit_log() with hash chain
- [x] `routers/auth.py` — refactored to use shared audit_writer
- [x] `routers/hospitals.py` — GET /hospitals (no auth)
- [x] `routers/patients.py` — paginated list + Soundex+regex search + phoneticMatch, CRUD with audit
- [x] `routers/records.py` — AES encrypt on create, CP-ABE check + decrypt on get, flag toggle
- [x] `routers/users.py` — paginated list, create (bcrypt+ECDH), update, dual-write revocation
- [x] `routers/consents.py` — list (role-filtered), grant, revoke (soft-delete)
- [x] `routers/audit.py` — paginated log (newest first), full hash chain verify
- [x] `routers/exchange.py` — list, create, approve (encrypted payload), reject
- [x] `routers/crypto_demo.py` — encrypt-demo, decrypt-demo, ecdh-demo (no auth)

### HARDCODE items introduced:
| Item | File | Change for production |
|---|---|---|
| `_STATIC_SALT = b"EHR-SALT-2024-STATIC"` | records.py, exchange.py, crypto_demo.py | Per-record random salt stored alongside iv |
| Single demo key for all records | records.py | Per-record DEK wrapped by KMS |
| Simulated exchange payload (no real ECDH per-transfer) | exchange.py | Use derive_shared_secret() per request |
| Audit verify loads all logs into memory | audit.py | Cursor-based streaming for large datasets |

### Verification:
- [ ] `docker compose up --build` succeeds
- [ ] POST /auth/login returns JWT
- [ ] POST /patients creates patient with soundexCode
- [ ] GET /patients?search=sharma returns phoneticMatch entries
- [ ] POST /records encrypts content
- [ ] GET /records/{id} decrypts for authorized, 403 for unauthorized
- [ ] GET /audit/verify returns intact=true
- [ ] POST /crypto/ecdh-demo returns sharedSecretMatch=true

---

### Frontend tasks completed:
- [x] `src/store/authStore.ts` — Zustand: token, user, login, logout, persisted localStorage
- [x] `src/api/client.ts` — Axios + JWT interceptor + 401 redirect
- [x] `src/pages/Login.tsx` — form, calls POST /auth/login, Available Accounts dropdown
- [x] Protected route wrapper in App.tsx + React Router setup
- [x] `src/components/layout/Sidebar.tsx`
- [x] `src/components/layout/Header.tsx`
- [x] `src/components/layout/SecurityBanner.tsx`
- [x] `src/components/ui/Badge.tsx`, `Modal.tsx`, `Spinner.tsx`
- [x] `src/pages/Dashboard.tsx`
- [x] `src/pages/Patients.tsx` — list + phonetic search, Admin-only creation
- [x] `src/pages/PatientDetail.tsx`
- [x] `src/pages/Records.tsx` — create + view (with decrypted content)
- [x] `src/pages/AuditTrail.tsx`
- [x] `src/pages/Exchange.tsx`
- [x] `src/pages/UserManagement.tsx` (admin only)
- [x] `src/pages/EncryptionLab.tsx` — calls /crypto/* demo endpoints
- [x] `src/pages/Settings.tsx`
- [x] `src/pages/Timeline.tsx` — Patient-centric unified medical file

### Verification:
- [x] `docker exec ehr_backend python seed.py` prints "Seeding complete"
- [x] Login with dr.priya@citygeneral.in / Password@123 returns JWT
- [x] GET /patients returns 8 patients with soundexCodes
- [x] GET /patients?search=sharma returns Srihari with phoneticMatch=true
- [x] GET /records returns 32 records (no decrypted content)
- [x] GET /records/{id} with doctor token decrypts successfully
- [x] GET /audit/verify returns intact=true (37 entries verified)
- [x] GET /exchange returns 3 requests

---

## Phase 5 — Wiring + Final Fixes ✅ COMPLETE (Block 6)

**Goal:** Everything works end-to-end. Backend hardened. README written.

### Completed:
- [x] `POST /users/{id}/rotate-keys` — ECDH keypair rotation with audit log + fingerprint response
- [x] `main.py` v0.3.0 — 404/500 global handlers, generic Exception handler, startup banner
- [x] `docker-compose.yml` — removed `version:` key, backend Python healthcheck, seed service, DEMO_ENCRYPTION_PASSWORD env var
- [x] `README.md` — full project documentation with setup, credentials, security features, architecture
- [x] **Bug fix:** `audit.py` verify formula used `entry.action` (printed as `AuditAction.LOGIN`) instead of `entry.action.value` (`LOGIN`) — this caused ALL seeded entries to fail verification. Fixed.
- [x] **Bug fix:** `bcrypt==4.0.1` pinned — newer bcrypt removes `__about__` module breaking passlib
- [x] **Bug fix:** Frontend Dockerfile `chmod 777 /app` — fixed Vite EACCES timestamp file error

### Verified (automated checks):
- [x] `GET /health` → `{"status":"ok"}`
- [x] Login as dr.priya → JWT with role=doctor
- [x] `GET /audit/verify` → intact=true, 37/37 entries verified
- [x] Nurse accessing doctor-only record → 403 Access Denied
- [x] AES encrypt + decrypt roundtrip → plaintext matches
- [x] ECDH sharedSecretMatch → true
- [x] `POST /users/{id}/rotate-keys` → new fingerprint returned

---

## Phase 6 — File Attachments & Unified Workflow ✅ COMPLETE

**Goal:** Transform the platform into a document-centric system with a real-world consultation/hospital workflow.

### Tasks completed:
- [x] **File Support:** Added Base64 serialization for PDF/Image attachments. Bundled into encrypted AES-256-GCM payload.
- [x] **Doctor Workflow:** Redefined as "Consult Patient". Doctors search by 10-digit ID and create `pending` cases.
- [x] **Hospital Workflow:** Dedicated `hospital@hospital.in` account for clerks. Approve/Reject doctor cases before they hit the timeline.
- [x] **Patient IDs:** Migrated from UUIDs to user-friendly, unique 10-digit numeric identifiers.
- [x] **Timeline UX:** Added Date/Time picker for records to allow backdating reports to the actual consultation time.
- [x] **Persistence:** Fixed auth state initialization bug to prevent redirect-to-login on page refresh.
- [x] **Documentation:** Updated all docs (Architecture, API, Security, Frontend, Backend) to reflect the new system state.

### Verification:
- [x] Uploaded a PDF via Timeline → successfully stored and decrypted.
- [x] Logged in as `hospital@hospital.in` → saw pending cases and approved them.
- [x] Refreshed the dashboard → session persisted correctly.
- [x] Search for a patient by 10-digit ID → instant match.
- [x] Verified `audit/verify` remains intact after manual file injections and workflow changes.

---

## Known Issues / Technical Debt

| Issue | Severity | Notes |
|---|---|---|
| JWT_SECRET hardcoded in docker-compose.yml | Low (dev only) | Move to .env before sharing |
| No token blacklist (revoked users keep existing tokens for up to 8h) | Medium | Add Redis blacklist for instant invalidation |
| No rate limiting on auth endpoints | Medium | Add slowapi middleware |
| Static PBKDF2 salt for all records | High (prod) | Replace with per-record random salt stored alongside IV |
| Private keys stored as plaintext PEM | High (prod) | Wrap with HSM/KMS before production |

---

## How to Update This File

At the end of every phase:
1. Move the completed phase section to ✅ COMPLETE
2. Check off all completed items with `[x]`
3. Add any new items discovered during that phase
4. Add any new issues to the Known Issues table
5. Update "Last updated" at the top of API_REFERENCE.md
