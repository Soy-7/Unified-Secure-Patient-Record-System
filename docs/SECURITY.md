# Security Model

This document explains every security decision in plain English.
**Last updated: Phase 6 — File Attachments & Unified Patient Workflow implemented.**

---

## The 7 Security Pillars — Current Status

| Pillar | Planned | Implemented |
|---|---|---|
| bcrypt password hashing | ✓ | ✅ `crypto/hashing.py` |
| AES-256-GCM record encryption | ✓ | ✅ `crypto/aes.py` + `routers/records.py` |
| JWT short-expiry authentication | ✓ | ✅ `routers/auth.py` + `dependencies.py` |
| CP-ABE access policy check | ✓ | ✅ `routers/records.py` — `can_access()` |
| Audit hash chain | ✓ | ✅ `utils/audit_writer.py` + `routers/audit.py` |
| User revocation | ✓ | ✅ `routers/users.py` + `dependencies.py` |
| Role-based route guards (backend) | ✓ | ✅ `dependencies.py` — `role_required()` |

---

## 1. Password Storage — bcrypt (NOT plain SHA-256)

**Why bcrypt?**
bcrypt is *intentionally slow* — takes ~100ms per check by design.
SHA-256 runs millions of times per second → trivially brute-forceable.

**Implementation (in `crypto/hashing.py`):**
```python
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

hash_password("mypassword")     # → "$2b$12$..."
verify_password("mypassword", stored_hash)  # → True/False (constant time)
```

Cost factor 12 = ~100ms per check on modern hardware.
> ⚠ **HARDCODE**: Increase to 13–14 for production servers with more CPU.

**Rule:** Passwords are only ever touched in `crypto/hashing.py`.
Never call bcrypt or SHA-256 for passwords anywhere else.

---

## 2. Record Encryption — AES-256-GCM

**How it works in `crypto/aes.py` + `routers/records.py`:**

```
1. Key derivation (once per request):
   key = PBKDF2-HMAC-SHA256("EHR-DEMO-KEY-2024", b"EHR-SALT-2024-STATIC", 100_000 iterations)
   → 32-byte key

2. Encrypt (POST /records):
   iv = os.urandom(12)            ← 12 fresh random bytes EVERY TIME
   ct_and_tag = AESGCM(key).encrypt(iv, plaintext, None)
   ciphertext = ct_and_tag[:-16]  ← GCM separates tag from ciphertext
   tag        = ct_and_tag[-16:]  ← 16-byte authentication tag

3. Storage in MongoDB:
   encryptedContent = base64(ciphertext + tag)  ← combined
   iv               = base64(iv)                ← separate field

4. Decrypt (GET /records/{id}):
   ct_and_tag = base64decode(encryptedContent)
   ciphertext = ct_and_tag[:-16]
   tag        = ct_and_tag[-16:]
   plaintext  = AESGCM(key).decrypt(iv, ciphertext + tag, None)
   ↑ If tag doesn't match → InvalidTag exception → tamper detected
```

**Why GCM?**
GCM provides both **confidentiality** (no one can read it) and **integrity** (no one can modify it without detection). The 16-byte tag is a MAC — if any byte of the ciphertext changes, decryption fails with `InvalidTag`.

**File Attachment Security:**
Files are not stored raw on the filesystem. They are converted to **Base64** and bundled inside a JSON object:
`{"text": "...", "fileName": "...", "fileData": "data:base64..."}`
This entire JSON string is then encrypted using the AES-256-GCM mechanism described above. This ensures files have the exact same cryptographic protection and access policy as the text notes.

> ⚠ **HARDCODE**: 
> - `b"EHR-SALT-2024-STATIC"` is the same for ALL records. In production: unique salt per record, stored alongside `iv`.
> - `"EHR-DEMO-KEY-2024"` is a single master password. In production: per-record DEK wrapped by a KMS.
> - 100,000 PBKDF2 iterations. NIST recommends 600,000+ for SHA-256 in 2023.

---

## 3. JWT Tokens — Short Expiry, Role Embedded

**Implementation (in `routers/auth.py`):**
```python
payload = {
    "sub":         user.id,
    "email":       user.email,
    "role":        user.role.value,       # "doctor", "admin", etc.
    "hospital_id": user.hospitalId,
    "attributes":  user.attributes,       # CP-ABE attributes embedded
    "exp":         now + timedelta(hours=8),
}
token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
```

**Security properties:**
- 8-hour expiry — stolen token becomes useless in max 8 hours
- Role in token — no DB query needed for role-based guards
- Attributes in token — CP-ABE check uses these (backed up by DB lookup)
- Signed with `JWT_SECRET` — any payload modification breaks the signature

> ⚠ **HARDCODE**:
> - `HS256` (symmetric) — use `RS256` (asymmetric) for multi-service production
> - `jwt_secret` has a weak default — set via env var before sharing with anyone
> - No `jti` claim — cannot blacklist individual tokens on logout

---

## 4. CP-ABE Access Control — Server-Side Only

**Implementation (in `routers/records.py`):**
```python
def can_access(user_attributes: list[str], record_policy: list[str]) -> bool:
    return all(attr in user_attributes for attr in record_policy)

# Example:
# record.accessPolicy = ["doctor", "hospital-001"]
# user.attributes     = ["doctor", "hospital-001", "oncology"]
# can_access() → True  (user has ALL required attrs)

# record.accessPolicy = ["doctor", "hospital-001"]
# user.attributes     = ["nurse", "hospital-001"]
# can_access() → False (user is missing "doctor")
```

**When it fails — the 403 body:**
```json
{
  "detail": "Access Denied",
  "message": "Your credential attributes ['nurse', 'hospital-001'] do not satisfy the required access policy ['doctor', 'hospital-001'] for this record.",
  "userAttributes": ["nurse", "hospital-001"],
  "requiredPolicy": ["doctor", "hospital-001"]
}
```

This tells the user exactly which attributes they're missing, so they can request appropriate consent.

**Critical:** The frontend hides the "View Record" button for unauthorized users, but the backend **always** runs `can_access()` on `GET /records/{id}`. The frontend check is UX only.

**Edge case:** Empty policy `[]` → `all()` of empty iterable = `True` → everyone can access. Use this deliberately for public/non-sensitive records.

---

## 5. Audit Hash Chain — Tamper Detection

**Implementation (in `utils/audit_writer.py`):**
```python
# Every write call:
entry_data = f"{user_id}{action}{resource_type}{resource_id}{timestamp}{details}"
entry_hash = sha256_hex(prev_hash + entry_data)

# Genesis (first-ever entry): prev_hash = "0" * 64
```

**How tampering is detected (`GET /audit/verify`):**
```
Entry 1: prevHash="0000...", hash=SHA256("0000..." + entry1_data)
Entry 2: prevHash=Entry1.hash, hash=SHA256(Entry1.hash + entry2_data)
Entry 3: prevHash=Entry2.hash, hash=SHA256(Entry2.hash + entry3_data)
```

If Entry 2 is modified → Entry 2's hash changes → Entry 3's `prevHash` doesn't match → chain breaks → `brokenAt = Entry3.id`.

> ⚠ **Important maintenance rule:** The `entry_data` formula in `audit_writer.py` and in `GET /audit/verify` must ALWAYS be identical. Changing one without the other breaks verification for all future entries.

---

## 6. User Revocation — Instant Block

**Implementation (in `routers/users.py`):**
```python
# Dual write on POST /users/{id}/revoke:
await db[USERS].update_one({"id": user_id}, {"$set": {"isRevoked": True}})
await db[REVOCATION_LIST].insert_one({
    "userId": user_id, "reason": reason,
    "revokedAt": now, "revokedBy": current_user.id
})
```

**Where it's checked (in `dependencies.py` — `get_current_user`):**
1. Decodes JWT → gets `user_id`
2. Queries `revocation_list` for `userId` → 403 if found
3. Fetches user document → checks `isRevoked` flag → 403 if True

Both checks run on **every authenticated request**.

> ⚠ **HARDCODE**: Existing JWT tokens remain valid until they expire (max 8h after revocation). For instant invalidation: add a Redis blacklist using JWT's `jti` claim.

---

## 7. Role-Based Route Guards — Backend Enforced

**Implementation (in `dependencies.py`):**
```python
def role_required(*roles: str):
    async def _check(user: UserInDB = Depends(get_current_user)) -> UserInDB:
        if user.role.value not in roles:
            raise HTTPException(403, f"Required role: {' or '.join(roles)}")
        return user
    return _check
```

**Usage in routers:**
```python
# Single role:
@router.get("/users", dependencies=[Depends(role_required("admin"))])

# Multiple roles:
@router.post("/records", dependencies=[Depends(role_required("doctor", "admin"))])
```

Role reference:
| Role | Can do |
|---|---|
| `admin` | **Hospital Staff / Admin** — Register patients, approve pending records from doctors, manage users, view all data, revoke access. |
| `doctor` | **Medical Practitioner** — View patients, consult patients by creating "Cases" (creates `pending` records), view authorized records. |
| `nurse` | **Support Staff** — View patients and records (policy-gated). Same as doctor but cannot initiate new cases. |
| `patient` | **Self-Service** — View their own records, upload documents directly to their timeline (bypass approval). |

---

## CORS Configuration

```python
allow_origins=["http://localhost:5173"]
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```

> ⚠ **HARDCODE**: Add your production domain before deployment:
> ```python
> allow_origins=["http://localhost:5173", "https://ehr.yourhospital.com"]
> ```

---

## What's Not Implemented Yet (and Why)

| Feature | Status | Notes |
|---|---|---|
| HTTPS | Not in scope | Docker Compose is local dev. Production: Nginx + Let's Encrypt in front |
| JWT token blacklist | Not yet | Logout writes audit log only. Redis `jti` blacklist = Phase 5 |
| Rate limiting | Not yet | Add `slowapi` middleware in Phase 5 |
| Real ECDH per-exchange key | Partially | `crypto/ecdh.py` is complete. Exchange router uses demo AES key for now |
| Per-record random salt | Not yet | Using `STATIC_SALT` — production needs per-record salt stored with `iv` |
| Real IP extraction | Not yet | `get_simulated_ip()` returns fake IPs — replace with request header in prod |

---

## HARDCODE Tracker

All places where a value must be changed before production:

| Item | File | Current value | Production change |
|---|---|---|---|
| `JWT_SECRET` | `docker-compose.yml` | `ehr-super-secret-jwt-key-2024` | 32-byte random hex |
| `JWT_ALGORITHM` | `config.py` | `HS256` | `RS256` (asymmetric) |
| `DEMO_ENCRYPTION_PASSWORD` | `config.py` | `EHR-DEMO-KEY-2024` | KMS-managed key |
| `_STATIC_SALT` | `records.py`, `exchange.py`, `crypto_demo.py` | `b"EHR-SALT-2024-STATIC"` | Per-record random bytes |
| PBKDF2 iterations | `crypto/aes.py` | 100,000 | 600,000+ |
| bcrypt rounds | `crypto/hashing.py` | 12 | 13–14 |
| HKDF salt | `crypto/ecdh.py` | `None` (static) | Session nonce |
| IP address | `dependencies.py` | Simulated | `X-Forwarded-For` header |
| CORS origin | `main.py` | `localhost:5173` only | Add production domain |
| Hospital `apiEndpoint` | Seeded manually | Hardcoded in seed | Registered via onboarding API |
| Token blacklist | Missing | None | Redis with `jti` + TTL |
