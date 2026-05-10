# API Reference

Complete list of all API endpoints with their current implementation status.

**Last updated: Phase 6 — File Attachments & Unified Patient Workflow implemented.**

---

## Base URL & Auth

```
Dev server:  http://localhost:8000
Via Vite:    http://localhost:5173/api   (proxy strips /api prefix)

All protected routes require:
  Authorization: Bearer <jwt_token>

Get a token: POST /auth/login
```

### Status key
- ✅ **Implemented** — works right now
- 🔲 **Planned** — scaffold only, returns 200 with no data yet

---

## System

| Method | URL | Auth | Status | Notes |
|---|---|---|---|---|
| GET | `/health` | None | ✅ | `{"status":"ok","service":"EHR Platform"}` |
| GET | `/docs` | None | ✅ | Swagger UI — use Authorize button to test |
| GET | `/redoc` | None | ✅ | ReDoc documentation |

---

## Authentication — `/auth`

| Method | URL | Auth | Role | Status |
|---|---|---|---|---|
| POST | `/auth/login` | None | — | ✅ |
| POST | `/auth/logout` | JWT | Any | ✅ |

### POST /auth/login

Uses `OAuth2PasswordRequestForm` (form body, not JSON).

**Request (form body):**
```
username=doctor@hospital.com
password=SecurePassword123
```

**Response 200:**
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "name": "Dr. Smith",
    "email": "doctor@hospital.com",
    "role": "doctor",
    "hospitalId": "hosp-001",
    "department": "Oncology",
    "attributes": ["doctor", "hospital-001", "oncology"],
    "publicKey": "-----BEGIN PUBLIC KEY-----...",
    "createdAt": "2024-01-01T00:00:00+00:00",
    "isRevoked": false
  }
}
```

**Response 401:** `"Access denied — credentials not recognised"`
**Response 403:** `"Your account access has been revoked. Contact your administrator."`

### POST /auth/logout

**Response 200:**
```json
{ "message": "Logged out successfully" }
```

> Note: JWT is not server-invalidated (stateless design). Client must discard the token.

---

## Patients — `/patients`

| Method | URL | Auth | Role | Status |
|---|---|---|---|---|
| GET | `/patients` | JWT | Any | ✅ |
| POST | `/patients` | JWT | admin | ✅ |
| GET | `/patients/{id}` | JWT | Any | ✅ |
| PUT | `/patients/{id}` | JWT | admin | ✅ |

### GET /patients — Query params

| Param | Type | Default | Description |
|---|---|---|---|
| `search` | string | — | Name search. Runs Soundex AND case-insensitive regex simultaneously |
| `hospital_id` | string | — | Filter by `primaryHospitalId` or `linkedHospitalIds` |
| `page` | int | 1 | Page number (1-indexed) |
| `limit` | int | 10 | Results per page (max 100) |

**Response 200:**
```json
{
  "patients": [
    {
      "id": "uuid",
      "soundexCode": "S650",
      "name": "Sharma Raj",
      "phoneticMatch": true,
      ...
    }
  ],
  "total": 42,
  "page": 1,
  "pages": 5
}
```

`phoneticMatch: true` means the Soundex index was the reason this patient appeared.

### POST /patients — Request body

```json
{
  "id": "1948572019", // Optional — will be auto-generated as 10-digit numeric if null
  "name": "John Smith",
  "dob": "1985-03-22",
  "gender": "male",
  "bloodGroup": "O+",
  "phone": "+91-9876543210",
  "email": "john@example.com",
  "address": "123 Main St, Mumbai",
  "primaryHospitalId": "hosp-001",
  "emergencyContact": {
    "name": "Jane Smith",
    "relation": "spouse",
    "phone": "+91-9999999999"
  }
}
```

### PUT /patients/{id}

Only these fields can be updated (others are ignored):
`name`, `dob`, `gender`, `bloodGroup`, `phone`, `email`, `address`, `emergencyContact`

If `name` is updated, `soundexCode` is automatically recomputed.

---

## Records — `/records`

| Method | URL | Auth | Role | Status |
|---|---|---|---|---|
| GET | `/records` | JWT | Any | ✅ |
| POST | `/records` | JWT | Any | ✅ |
| GET | `/records/{id}` | JWT | Any | ✅ |
| PUT | `/records/{id}/flag` | JWT | admin | ✅ |
| PUT | `/records/{id}/status` | JWT | admin | ✅ |

### GET /records — Query params

| Param | Type | Description |
|---|---|---|
| `patient_id` | string | Filter by patient |
| `hospital_id` | string | Override hospital filter |
| `record_type` | string | One of: `diagnosis`, `prescription`, `lab_result`, `imaging`, `discharge_summary`, `consultation` |
| `status` | string | Filter by `pending` or `approved` |
| `page` | int | Default 1 |
| `limit` | int | Default 10, max 100 |

List view returns metadata only — `decryptedContent` is always null here.

### POST /records — Request body

```json
{
  "patientId": "1948572019",
  "hospitalId": "hosp-001",
  "recordType": "lab_result",
  "title": "Blood Panel — January 2024",
  "content": "{ \"text\": \"...\", \"fileName\": \"results.pdf\", \"fileData\": \"data:application/pdf;base64,...\" }",
  "recordDate": "2024-01-20T10:00:00Z",
  "accessPolicy": ["doctor", "hospital-001"],
  "tags": ["routine", "hematology"]
}
```

`content` is a stringified JSON object that can contain text and Base64 file data.
`recordDate` (optional) allows backdating the record to the actual consultation time.

**Workflow Note:** 
- If created by a **Doctor**, the record status is set to `pending`.
- If created by a **Hospital Admin/Staff** or **Patient**, it is set to `approved` immediately.
- `pending` records only become visible in the patient's unified timeline once approved by the hospital.

**Response 201:** Returns `EHRRecordInDB`.

### GET /records/{id} — CP-ABE Response

**If authorised (200):**
```json
{
  "id": "uuid",
  "title": "Blood Panel",
  "encryptedContent": "base64...",
  "iv": "base64...",
  "accessPolicy": ["doctor", "hospital-001"],
  "decryptedContent": "{ \"WBC\": 7.2, \"RBC\": 4.8 }",
  ...
}
```

**If CP-ABE check fails (403):**
```json
{
  "detail": "Access Denied",
  "message": "Your credential attributes ['nurse', 'hospital-001'] do not satisfy the required access policy ['doctor', 'hospital-001'] for this record.",
  "userAttributes": ["nurse", "hospital-001"],
  "requiredPolicy": ["doctor", "hospital-001"]
}
```

---

## Users — `/users` (admin only)

| Method | URL | Auth | Role | Status |
|---|---|---|---|---|
| GET | `/users` | JWT | admin | ✅ |
| POST | `/users` | JWT | admin | ✅ |
| PUT | `/users/{id}` | JWT | admin | ✅ |
| POST | `/users/{id}/revoke` | JWT | admin | ✅ |

### POST /users — Request body

```json
{
  "name": "Dr. Jane Doe",
  "email": "jane@hospital.com",
  "password": "TempPassword123",
  "role": "doctor",
  "hospitalId": "hosp-001",
  "department": "Cardiology",
  "attributes": ["doctor", "hospital-001", "cardiology"]
}
```

`attributes` is the CP-ABE attribute list checked against `accessPolicy` on records.

### PUT /users/{id}

Updatable fields only: `name`, `department`, `attributes`.
Other fields are silently ignored.

### POST /users/{id}/revoke

```json
{ "reason": "Employee terminated on 2024-01-15" }
```

**Response 200:** `{ "message": "User access revoked successfully" }`

Two writes happen: `users.isRevoked = True` AND a new `revocation_list` document.

---

## Consents — `/consents`

| Method | URL | Auth | Role | Status |
|---|---|---|---|---|
| GET | `/consents/patient/{id}` | JWT | Any | ✅ |
| POST | `/consents` | JWT | doctor, admin | ✅ |
| DELETE | `/consents/{id}` | JWT | doctor, admin | ✅ |

### POST /consents — Request body

```json
{
  "patientId": "uuid",
  "grantedTo": "hosp-002",
  "grantedToType": "hospital",
  "recordIds": ["*"],
  "permissions": ["read", "share"],
  "validFrom": "2024-01-01T00:00:00Z",
  "validUntil": "2024-12-31T23:59:59Z"
}
```

`recordIds: ["*"]` means all records for this patient.

### DELETE /consents/{id}

Sets `isRevoked=True` and `revokedAt=now`. Record is not deleted (preserved for audit).
Returns 409 if already revoked.

---

## Audit — `/audit` (admin only)

| Method | URL | Auth | Role | Status |
|---|---|---|---|---|
| GET | `/audit` | JWT | admin | ✅ |
| GET | `/audit/verify` | JWT | admin | ✅ |

### GET /audit — Query params

| Param | Values | Description |
|---|---|---|
| `action` | `VIEW`, `CREATE`, `UPDATE`, `DELETE`, `SHARE`, `EXPORT`, `LOGIN`, `LOGOUT`, `ACCESS_DENIED` | Filter by action |
| `user_id` | uuid string | Filter by user |
| `hospital_id` | string | Filter by hospital |
| `date_from` | ISO-8601 | Start of date range |
| `date_to` | ISO-8601 | End of date range |
| `page` | int | Default 1 |
| `limit` | int | Default 20, max 100 |

Results are returned newest first.

### GET /audit/verify

```json
{
  "total": 1247,
  "verified": 1247,
  "failed": 0,
  "intact": true,
  "brokenAt": null
}
```

On tamper detection:
```json
{
  "total": 1247,
  "verified": 843,
  "failed": 404,
  "intact": false,
  "brokenAt": "uuid-of-first-broken-entry"
}
```

---

## Exchange — `/exchange`

| Method | URL | Auth | Role | Status |
|---|---|---|---|---|
| GET | `/exchange` | JWT | Any | ✅ |
| POST | `/exchange` | JWT | doctor, admin | ✅ |
| PUT | `/exchange/{id}/approve` | JWT | doctor, admin | ✅ |
| PUT | `/exchange/{id}/reject` | JWT | doctor, admin | ✅ |

### GET /exchange — Query params

| Param | Values | Description |
|---|---|---|
| `status` | `pending`, `approved`, `rejected`, `completed` | Filter by status |

Returns requests where `fromHospitalId` OR `toHospitalId` matches the current user's hospital.

### POST /exchange — Request body

```json
{
  "toHospitalId": "hosp-002",
  "patientId": "uuid",
  "recordTypes": ["lab_result", "imaging"],
  "purpose": "Patient transferred for specialist consultation"
}
```

### PUT /exchange/{id}/approve

No request body needed. On approval:
1. Fetches patient records of requested types
2. Encrypts JSON summary with demo AES key
3. Sets `status = completed`, `encryptedPayload` = encrypted data, `resolvedAt` = now

Returns 409 if request is not in `pending` status.

---

## Hospitals — `/hospitals`

| Method | URL | Auth | Role | Status |
|---|---|---|---|---|
| GET | `/hospitals` | None | — | ✅ |

No auth required. Returns all hospitals as `HospitalResponse` list.

---

## Crypto Demo — `/crypto`

No authentication required on any of these routes.

| Method | URL | Status |
|---|---|---|
| POST | `/crypto/encrypt-demo` | ✅ |
| POST | `/crypto/decrypt-demo` | ✅ |
| POST | `/crypto/ecdh-demo` | ✅ |

### POST /crypto/encrypt-demo

```json
{ "text": "Hello, World!" }
```

**Response:**
```json
{
  "ciphertext": "base64(ciphertext + tag combined)...",
  "iv": "base64_of_12_byte_iv...",
  "algorithm": "AES-256-GCM",
  "keyLength": 256
}
```

### POST /crypto/decrypt-demo

```json
{
  "ciphertext": "base64_from_encrypt_demo...",
  "iv": "base64_iv_from_encrypt_demo..."
}
```

**Response:** `{ "plaintext": "Hello, World!" }`

### POST /crypto/ecdh-demo

No request body needed.

**Response:**
```json
{
  "hospitalA": {
    "publicKey": "-----BEGIN PUBLIC KEY-----...",
    "fingerprint": "aB3kLmNoPqRsTuVw..."
  },
  "hospitalB": {
    "publicKey": "-----BEGIN PUBLIC KEY-----...",
    "fingerprint": "xY9zAbCdEfGhIjKl..."
  },
  "sharedSecretMatch": true,
  "sharedSecretPreview": "K3mNpQrStUvWxYzA..."
}
```

`sharedSecretMatch` should always be `true` — this proves ECDH is working correctly.

---

## HTTP Status Codes

| Code | Meaning | When |
|---|---|---|
| 200 | OK | Successful GET, PUT, POST /logout |
| 201 | Created | Successful POST (patient, record, user, consent, exchange) |
| 400 | Bad Request | Empty input, no updatable fields |
| 401 | Unauthorized | Missing/expired/malformed JWT |
| 403 | Forbidden | Valid JWT but wrong role, revoked account, or CP-ABE policy failure |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Duplicate email, already revoked, status not pending |
| 422 | Unprocessable Entity | Pydantic validation failed (FastAPI automatic) |
| 500 | Internal Server Error | Unexpected error (decryption failure, DB issue) |
