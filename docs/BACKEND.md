# Backend Code Walkthrough

Everything inside the `backend/` folder explained file by file.
**Last updated: Phase 6 — File Attachments & Unified Patient Workflow implemented.**

---

## Folder Map

```
backend/
├── main.py           ← FastAPI app entry (v0.2.0)
├── config.py         ← Env vars + settings singleton
├── database.py       ← Motor client + collection constants
├── dependencies.py   ← get_current_user, role_required, get_simulated_ip
├── seed.py           ← One-time DB seeding script (scaffold, not yet filled)
│
├── models/           ← Pydantic schemas (3-tier per resource)
│   ├── user.py       ← UserRole, UserCreate, UserInDB, UserResponse, TokenResponse
│   ├── patient.py    ← PatientCreate, PatientInDB, PatientResponse
│   ├── record.py     ← RecordType, RecordCreate, EHRRecordInDB, RecordResponse
│   ├── audit.py      ← AuditAction, AuditResourceType, AccessLogInDB/Response
│   ├── consent.py    ← ConsentCreate, ConsentInDB, ConsentResponse
│   ├── hospital.py   ← HospitalInDB, HospitalResponse
│   └── exchange.py   ← ExchangeStatus, ExchangeRequestCreate/InDB/Response
│
├── routers/          ← One file per URL group — all fully implemented
│   ├── auth.py       ← /auth/login, /auth/logout
│   ├── patients.py   ← /patients CRUD + Soundex search
│   ├── records.py    ← /records AES encrypt/decrypt + CP-ABE check
│   ├── users.py      ← /users admin management + revocation
│   ├── consents.py   ← /consents grant/revoke
│   ├── audit.py      ← /audit log + chain verify
│   ├── exchange.py   ← /exchange inter-hospital requests
│   ├── hospitals.py  ← /hospitals registry
│   └── crypto_demo.py← /crypto Encryption Lab demo
│
├── crypto/           ← Pure utility functions (no FastAPI deps, testable standalone)
│   ├── aes.py        ← AES-256-GCM encrypt/decrypt + PBKDF2 key derivation
│   ├── ecdh.py       ← ECDH P-256 key pair + shared secret (HKDF)
│   ├── hashing.py    ← bcrypt password hash/verify + SHA-256 audit chain
│   └── soundex.py    ← Soundex phonetic algorithm for patient name search
│
└── utils/
    └── audit_writer.py ← Shared write_audit_log() — imported by all routers
```

---

## Entry Point — `main.py`

- FastAPI `v0.2.0` — Phase 2 auth implemented
- Lifespan from `database.py` — MongoDB opened/closed with the app
- CORS locked to `http://localhost:5173` (Vite dev server)
- 9 routers mounted; `/health` probe always returns 200

---

## Configuration — `config.py`

Reads these env vars (all with safe defaults for local dev):

| Variable | Default | Purpose |
|---|---|---|
| `MONGODB_URL` | `mongodb://localhost:27017/ehrdb` | Motor connection string |
| `JWT_SECRET` | `change-me-before-any-real-deployment` | JWT signing key |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `JWT_EXPIRE_HOURS` | `8` | Token lifetime |
| `APP_NAME` | `EHR Platform` | Shown in docs + health check |
| `DEMO_ENCRYPTION_PASSWORD` | `EHR-DEMO-KEY-2024` | Master AES key password |

> **HARDCODE**: `DEMO_ENCRYPTION_PASSWORD` uses a single password for all records.
> Production needs a KMS (AWS KMS / HashiCorp Vault) with per-record DEKs.

Import the singleton: `from config import settings`

---

## Database — `database.py`

Motor async client with FastAPI lifespan. Collection name constants:

```python
USERS             = "users"
PATIENTS          = "patients"
RECORDS           = "records"
AUDIT_LOGS        = "audit_logs"
CONSENTS          = "consents"
HOSPITALS         = "hospitals"
EXCHANGE_REQUESTS = "exchange_requests"
REVOCATION_LIST   = "revocation_list"
```

Always import collection names from here — never hardcode strings in routers.

Usage in a router:
```python
from database import PATIENTS, get_database
docs = await db[PATIENTS].find(query).to_list(100)
```

---

## Dependencies — `dependencies.py`

Three reusable dependency functions:

### `get_current_user(token)`
1. Decodes the `Authorization: Bearer <token>` header
2. Extracts `sub` (user ID) from JWT payload
3. Checks `revocation_list` collection — 403 if found
4. Fetches full user from `users` collection
5. Checks `user.isRevoked` — 403 if True

### `role_required(*roles)`
Factory that returns a dependency. Usage:
```python
# Single role:
dependencies=[Depends(role_required("admin"))]

# Multiple roles:
dependencies=[Depends(role_required("doctor", "admin"))]
```

### `get_simulated_ip()`
Returns a random `192.168.x.x` string for audit logs.
> **HARDCODE**: Replace with `request.headers.get("X-Forwarded-For")` in production.

---

## Models — The 3-Tier Pattern

Every resource has three Pydantic models:

```
UserCreate   — what the API accepts (no id, no hash, no timestamps)
  ↓
UserInDB     — what's stored in MongoDB (all fields, including sensitive ones)
  ↓
UserResponse — what's returned to clients (sensitive fields stripped)
```

### Key field decisions by model:

**`patient.py`**
- `id` — Unique 10-digit numeric string (auto-generated if not provided)
- `soundexCode` — pre-computed at creation via `soundex(name)`, stored and indexed
- `linkedHospitalIds` — grows when inter-hospital exchange is approved

**`record.py`**
- `encryptedContent` — `base64(ciphertext_bytes + tag_bytes)` combined
- `iv` — `base64(12_random_bytes)` stored separately
- `decryptedContent` — only populated on `GET /records/{id}` if CP-ABE passes

**`audit.py`**
- `hash` — `SHA-256(prevHash + entry_data)` for this entry
- `prevHash` — hash of the previous entry (genesis = `"0" * 64`)

---

## Crypto Modules — `crypto/`

### `aes.py` — AES-256-GCM

```python
# Key derivation (called once per request, not stored)
key = derive_key_from_password("EHR-DEMO-KEY-2024", b"EHR-SALT-2024-STATIC")
# → 32-byte AES key via PBKDF2-HMAC-SHA256 (100,000 iterations)

# Encrypt — fresh IV every call!
enc = encrypt("plaintext data", key)
# → {"ciphertext": base64, "iv": base64, "tag": base64}

# Storage pattern in records collection:
# encryptedContent = base64(ciphertext_bytes + tag_bytes)  ← combined
# iv = enc["iv"]                                           ← separate field

# Decrypt
plaintext = decrypt(ct_b64, iv_b64, tag_b64, key)
# Raises InvalidTag if data was tampered with
```

### `ecdh.py` — ECDH P-256

```python
keys = generate_keypair()
# → {"publicKey": PEM string, "privateKey": PEM string}

shared_secret = derive_shared_secret(private_pem, peer_public_pem)
# → base64 of 32-byte HKDF-derived key (AES-256 ready)

fingerprint = get_key_fingerprint(public_pem)
# → first 32 chars of base64(SHA-256(public_pem))
```

### `hashing.py` — Passwords + Audit Chain

```python
# Passwords (bcrypt cost=12)
hashed   = hash_password("mypassword")
is_valid = verify_password("mypassword", hashed)  # → True/False

# Audit chain
hash = compute_audit_hash(prev_hash, entry_data)
# → sha256_hex(prev_hash + entry_data)

AUDIT_GENESIS_HASH  # = "0" * 64 — used as prevHash for the first-ever entry
```

### `soundex.py` — Phonetic Name Search

```python
soundex("Smith")   # → "S530"
soundex("Smyth")   # → "S530"  ← same! search finds both
soundex("Srihari") # → "S600"
soundex("Sharma")  # → "S650"
```

---

## Audit Writer — `utils/audit_writer.py`

Single shared function imported by every router:

```python
await write_audit_log(
    db=db,
    user=current_user,
    action=AuditAction.CREATE,
    resource_type=AuditResourceType.patient,
    resource_id=patient_id,
    hospital_id=current_user.hospitalId,
    ip_address=get_simulated_ip(),
    details="Created patient 'John Smith'",
)
```

Internally:
1. Fetches the last audit entry (by timestamp desc) to get `prevHash`
2. If no entries exist: `prevHash = AUDIT_GENESIS_HASH` (`"0" * 64`)
3. Builds `entry_data = userId + action + resourceType + resourceId + timestamp + details`
4. `entry_hash = sha256(prevHash + entry_data)`
5. Inserts the full `AccessLogInDB` document

> The `entry_data` formula in `audit_writer.py` and in `GET /audit/verify` **must always be identical** — they are the two halves of the tamper-detection system.

---

## Routers — What Each Does

### `auth.py` — `/auth`
| Method | Route | Auth | Notes |
|---|---|---|---|
| POST | `/auth/login` | None | OAuth2 form → bcrypt check → JWT → audit LOG |
| POST | `/auth/logout` | JWT | Writes audit log. JWT not server-invalidated (stateless) |

### `patients.py` — `/patients`
| Method | Route | Auth | Notes |
|---|---|---|---|
| GET | `/patients` | JWT | Any | Paginated. `?search=sharma` runs ID match + Soundex + regex simultaneously |
| POST | `/patients` | admin | Generates 10-digit ID. Computes soundexCode. Audit: CREATE |
| GET | `/patients/{id}` | JWT | Any | Audit: VIEW |
| PUT | `/patients/{id}` | admin | Field whitelist. Recomputes soundexCode if name changes |

Search response includes `phoneticMatch: true` when Soundex was the match mechanism.

### `records.py` — `/records`
| Method | Route | Auth | Notes |
|---|---|---|---|
| GET | `/records` | JWT | Any | Metadata only. Filterable by `status`. Sorted by `recordDate`. |
| POST | `/records` | Any | AES encrypts `content` (JSON with files). Dr → status=pending. |
| GET | `/records/{id}` | JWT | CP-ABE check → decrypt → return `decryptedContent` |
| PUT | `/records/{id}/status`| admin | Approve or reject a pending record |
| PUT | `/records/{id}/flag` | admin | Toggles `isFlagged` |

CP-ABE 403 body contains `userAttributes` and `requiredPolicy` for debugging.

### `users.py` — `/users` (admin only)
- Duplicate email check on create
- ECDH key pair generated per user
- Revocation: dual-write to `users.isRevoked` AND `revocation_list` collection

### `consents.py` — `/consents`
- Soft-delete on revoke (record preserved for audit trail)
- 409 if already revoked
- Nurses/patients filtered to their own hospital

### `audit.py` — `/audit` (admin only)
- `GET /audit` — paginated, newest first, filterable by action/user/hospital/date
- `GET /audit/verify` — walks entire chain oldest-first, recomputes every hash

### `exchange.py` — `/exchange`
- Approve: fetches records of requested types, encrypts JSON summary as payload
- Payload format: `base64(ciphertext + tag) + "|" + base64_iv`
- Status guard: 409 if approving/rejecting a non-pending request

### `hospitals.py` — `/hospitals`
- No auth. Single GET returns all hospitals. Used by login and exchange dropdowns.

### `crypto_demo.py` — `/crypto` (no auth)
- Encrypt/decrypt use same demo key as records (safe for demo only)
- ECDH demo generates two fresh key pairs per request, compares shared secrets
- Always returns `sharedSecretMatch: true` (proves ECDH correctness)

---

## API Docs (Auto-Generated)

FastAPI generates interactive docs from the code automatically:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

To test login in Swagger UI, click **Authorize** and enter email/password.
The "Authorize" button works because `auth.py` uses `OAuth2PasswordRequestForm`.
