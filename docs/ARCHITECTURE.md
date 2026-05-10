# Architecture Overview

This document explains how the EHR Platform is structured and why it's designed this way.
**Last updated: Phase 6 — File Attachments & Unified Patient Workflow implemented.**

---

## The 3 Services

```
Your Browser
     │
     │  http://localhost:5173
     ▼
┌─────────────────────────────┐
│   FRONTEND  (React + Vite)  │  ← What users see and interact with
│   Container: ehr_frontend   │     [scaffold only — Phase 4 will build UI]
│   Port: 5173                │
└─────────────────────────────┘
     │
     │  /api/* → http://backend:8000  (Vite proxy)
     ▼
┌─────────────────────────────┐
│   BACKEND  (FastAPI)        │  ← All 28 routes implemented ✅
│   Container: ehr_backend    │
│   Port: 8000                │
└─────────────────────────────┘
     │
     │  Motor async driver
     ▼
┌─────────────────────────────┐
│   DATABASE  (MongoDB 7)     │  ← 8 collections
│   Container: ehr_mongodb    │
│   Port: 27017               │
│   Volume: mongo_data        │  ← Data survives container restarts
└─────────────────────────────┘
```

---

## Login + Authenticated Request Flow

```
1. Doctor opens http://localhost:5173/login
   └── Enters email + password

2. Frontend POSTs form to /auth/login
   └── FastAPI validates with OAuth2PasswordRequestForm

3. Backend checks:
   ├── Find user by email in MongoDB (users collection)
   ├── Query revocation_list — if found → 403
   ├── bcrypt.verify(entered_password, stored_hash)
   └── user.isRevoked == True → 403

4. Backend issues JWT:
   { "sub": "user-uuid", "role": "doctor",
     "hospital_id": "hosp-001",
     "attributes": ["doctor", "hospital-001"],
     "exp": <8 hours from now> }
   └── Writes LOGIN entry to audit_logs (chained hash)

5. Frontend stores JWT and User data in Zustand store.
   └── Persisted in localStorage for session survival (reload/refresh).

6. All subsequent requests:
   Authorization: Bearer <jwt>
   └── get_current_user() runs on every protected route
```

---

## Record Encryption Flow

```
CREATE RECORD (POST /records)              READ RECORD (GET /records/{id})
──────────────────────────────             ──────────────────────────────
Doctor/Patient submits content             User requests record
(Content can include Base64 files)         

Backend:                                   Backend:
  key = PBKDF2("EHR-DEMO-KEY-2024",          Fetch doc from MongoDB
               b"EHR-SALT-2024-STATIC")       ↓
  iv  = os.urandom(12) ← FRESH!              JWT decoded → user.attributes
  ct_and_tag = AESGCM(key).encrypt(...)       ↓
  ciphertext = ct_and_tag[:-16]               can_access(user.attributes,
  tag        = ct_and_tag[-16:]                          record.accessPolicy)?
  ↓                                            ↓ No → 403 + audit ACCESS_DENIED
Store in MongoDB:                              ↓ Yes → decrypt:
  encryptedContent = base64(ct + tag)         ct_and_tag = b64decode(encContent)
  iv = base64(iv)                             ct  = ct_and_tag[:-16]
  status = "pending" (if Dr)                  tag = ct_and_tag[-16:]
  status = "approved" (if Hosp/Pat)           AESGCM(key).decrypt(iv, ct+tag)
  ↓                                          ↓
Write audit: action=CREATE                  Write audit: action=VIEW
Return EHRRecordInDB                        Return RecordResponse with
(no decryptedContent)                       decryptedContent populated
                                            (Frontend renders Base64 files)
```

### File Attachment Strategy
Instead of external S3 storage, the platform uses **Encrypted In-Document Storage**:
1. Frontend reads file → `Base64` string.
2. Bundles into JSON: `{"text": "...", "fileName": "...", "fileData": "base64..."}`.
3. Entire JSON blob is AES-256-GCM encrypted.
4. Maximum file size: ~10MB (limited by MongoDB's 16MB BSON limit).
```

---

## CP-ABE Policy Check

Policy check runs **server-side on every GET /records/{id}** — the frontend cannot bypass it.

```python
def can_access(user_attributes, record_policy):
    return all(attr in user_attributes for attr in record_policy)

# Example 1: Doctor reading their hospital's record
user.attributes = ["doctor", "hospital-001", "oncology"]
record.policy   = ["doctor", "hospital-001"]
can_access()    → True ✓

# Example 2: Nurse without doctor attribute
user.attributes = ["nurse", "hospital-001"]
record.policy   = ["doctor", "hospital-001"]
can_access()    → False → 403 response with:
{
  "userAttributes": ["nurse", "hospital-001"],
  "requiredPolicy": ["doctor", "hospital-001"]
}

# Example 3: Empty policy (open record)
record.policy = []
can_access()  → True ✓ (everyone can read)
```

---

## Audit Hash Chain

Every write action produces a chained audit log entry:

```
Entry 1 (genesis)
  userId:   "admin-uuid"
  action:   "LOGIN"
  prevHash: "0000000000000000000000000000000000000000000000000000000000000000"
  hash:     SHA256("0000..." + "admin-uuidLOGINsystem2024...")

Entry 2
  userId:   "doctor-uuid"
  action:   "CREATE"
  prevHash: Entry1.hash
  hash:     SHA256(Entry1.hash + "doctor-uuidCREATEpatient2024...")

Entry 3
  userId:   "doctor-uuid"
  action:   "VIEW"
  prevHash: Entry2.hash
  hash:     SHA256(Entry2.hash + "doctor-uuidVIEWrecord2024...")
```

`GET /audit/verify` walks all entries oldest-first and recomputes every hash.
If Entry 2 is modified → Entry 2's hash changes → Entry 3's `prevHash` fails → `brokenAt = Entry3.id`.

---

## Inter-Hospital Data Exchange

```
Hospital A (requesting)              Hospital B (target)
────────────────────────             ────────────────────
POST /exchange                       
  { toHospitalId: "hosp-B",          
    patientId: "...",                
    recordTypes: ["lab_result"] }   
  → status: pending                  

                                     GET /exchange
                                     → sees pending request

                                     PUT /exchange/{id}/approve
                                       1. Fetch patient records
                                       2. Build JSON summary
                                       3. Encrypt with demo AES key
                                       4. status = completed
                                          encryptedPayload = base64(ct+tag)|iv

Hospital A polls GET /exchange
→ sees status: completed
→ retrieves encryptedPayload
→ decrypts with demo key (same static key for now)
```

> **Production upgrade path:** Replace demo key with `derive_shared_secret()` from `crypto/ecdh.py`.
> Hospital A sends its ephemeral public key with the request; Hospital B derives the shared secret; unique key per exchange.

---

## Data Flow for Soundex Patient Search

```
Patient Creation:
  name = "Sharma Raj"
  id = "8374920182" (Unique 10-digit numeric ID)
  soundexCode = soundex("Sharma") = "S650"
  MongoDB: { name: "Sharma Raj", id: "8374920182", soundexCode: "S650", ... }

Search for "sharma" or "8374920182":
  search_code = soundex("sharma") = "S650"
  MongoDB query:
    { $or: [
        { id: "8374920182" },              ← exact ID match
        { soundexCode: "S650" },           ← index hit (fast phonetic)
        { name: /sharma/i }                ← regex scan (fallback)
      ]
    }
  Result: { ..., soundexCode: "S650", phoneticMatch: true }

Search for "sherma" (typo):
  soundex("sherma") = "S650"   ← same code!
  → still finds "Sharma Raj"
  phoneticMatch: true
```

---

## Revocation Flow

```
Admin calls POST /users/{id}/revoke:
  Write 1: users.isRevoked = True
  Write 2: revocation_list ← { userId, reason, revokedAt, revokedBy }
  Write 3: audit_logs ← ACCESS_DENIED-equivalent log

Revoked user tries to log in:
  POST /auth/login
    → find user by email ✓
    → check revocation_list → found → 403 immediately
    → JWT never issued

Revoked user's existing token (valid for up to 8h):
  GET /patients
    → get_current_user() → decode JWT → user_id extracted
    → query revocation_list → found → 403
    → request rejected even with valid token
```

---

## Network & Security Boundaries

```
Internet
   │
   │ (no direct access in dev)
   ▼
Docker bridge network: ehr_network
  ├── ehr_frontend (port 5173 exposed to host)
  │     └── /api/* proxied to ehr_backend:8000
  ├── ehr_backend (port 8000 exposed to host)
  │     ├── CORS: allow_origins=["http://localhost:5173"]
  │     └── Connects to ehr_mongodb:27017 (internal only)
  └── ehr_mongodb (port 27017 exposed to host for dev tools)
        └── Volume: mongo_data (persisted on host)

In production:
  - Only Nginx/load balancer exposed to internet
  - MongoDB NOT exposed externally
  - Backend only accessible via Nginx proxy
  - HTTPS everywhere
```

---

## MongoDB Collections

| Collection | Purpose | Key fields |
|---|---|---|
| `users` | Staff accounts | `email` (unique), `role`, `attributes`, `isRevoked` |
| `patients` | Patient registry | `soundexCode` (indexed), `primaryHospitalId` |
| `records` | Encrypted EHR records | `encryptedContent`, `iv`, `accessPolicy` |
| `audit_logs` | Immutable audit trail | `hash`, `prevHash`, `action`, `timestamp` |
| `consents` | Patient consent grants | `patientId`, `grantedTo`, `isRevoked` |
| `hospitals` | Hospital registry | `apiEndpoint`, `tlsCertFingerprint` |
| `exchange_requests` | Inter-hospital requests | `status`, `encryptedPayload` |
| `revocation_list` | Fast revocation lookup | `userId`, `reason`, `revokedBy` |
