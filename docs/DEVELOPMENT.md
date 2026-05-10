# Development Guide

How to run the project, make changes, and not break things.
**Last updated: Phase 6 — File Attachments & Unified Patient Workflow implemented.**

---

## Prerequisites

| Tool | Version | Download |
|---|---|---|
| Docker Desktop | Latest | https://www.docker.com/products/docker-desktop |
| Git | Any | https://git-scm.com |
| VS Code | Any | Recommended |

You do **not** need Python or Node installed locally — Docker handles everything.

---

## First-Time Setup

```bash
cd "c:\Users\sai_g\Web app\Mini Project Aprl\ehr-platform"
docker compose up --build
```

First build takes 3–5 minutes (downloading images, installing all packages).

### Verify it's working

| URL | Expected |
|---|---|
| http://localhost:8000/health | `{"status":"ok","service":"EHR Platform"}` |
| http://localhost:8000/docs | Swagger UI — click **Authorize** to test with JWT |
| http://localhost:5173 | "EHR Platform — Running" landing page |

---

## Daily Commands

```bash
# Start (no rebuild — fast, ~10 seconds)
docker compose up

# Start in background (detached — logs hidden)
docker compose up -d

# Watch logs from a specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f mongodb

# Stop (data preserved in mongo_data volume)
docker compose down

# Stop AND wipe all data (start fresh)
docker compose down -v

# Rebuild one service after Dockerfile/requirements.txt change
docker compose up --build backend
docker compose up --build frontend
```

---

## Making Backend Changes

Python files are **live-reloaded by Uvicorn** — no restart needed:

```
1. Edit backend/routers/patients.py
2. Uvicorn detects the file change (~1 second)
3. Your change is live at http://localhost:8000
```

**Rebuild required when:**
- You add a package to `requirements.txt`
- You change `backend/Dockerfile`

```bash
docker compose up --build backend
```

---

## Making Frontend Changes

Vite HMR (Hot Module Replacement) updates the browser in < 100ms:

```
1. Edit frontend/src/App.tsx
2. Browser updates automatically — no full page refresh
```

**Rebuild required when:**
- You add a package to `package.json`
- You change `frontend/Dockerfile`

```bash
docker compose up --build frontend
```

---

## Testing the API

### Option 1: Swagger UI (recommended)
1. Go to http://localhost:8000/docs
2. Click **Authorize**
3. Enter `username` (email) and `password` in the form
4. Click **Authorize** — Swagger will attach the JWT to all subsequent requests
5. Try any endpoint

### Option 2: curl

```bash
# Login and save token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d "username=admin@hospital.com&password=Admin1234!" \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Use the token
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/patients

# Create a patient
curl -X POST http://localhost:8000/patients \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"John Smith","dob":"1985-03-22","gender":"male","bloodGroup":"O+","phone":"+91-9876543210","address":"123 Main St","primaryHospitalId":"hosp-001","emergencyContact":{}}'
```

---

## Running the Seed Script

Populate MongoDB with all demo data (hospitals, users, patients, records, audit chain):

```bash
# Inside Docker (recommended — no local Python needed):
docker exec -it ehr_backend python seed.py

# Outside Docker (MongoDB must be reachable at localhost:27017):
cd backend
python seed.py
```

The script is **idempotent** — if the hospitals collection already has documents, it prints `"DB already seeded, skipping."` and exits without changing anything.

**Demo credentials (all passwords: `Password@123`):**

| Email | Role | Hospital |
|---|---|---|
| `superadmin@ehr.in` | Super Admin | City General |
| `admin@citygeneral.in` | Admin | City General |
| `hospital@hospital.in` | Hospital Front Desk (Admin) | City General |
| `dr.priya@citygeneral.in` | Doctor (Cardiology) | City General |
| `nurse.anitha@citygeneral.in` | Nurse | City General |
| `dr.vikram@apollo.in` | Doctor (Neurology) | Apollo |
| `srihari@patient.in` | Patient | City General |

**What gets seeded:**
- 3 hospitals, 6 users, 8 patients, 32 encrypted records
- 25 chained audit log entries (hash chain — verify with `GET /audit/verify`)
- 4 consents (3 active, 1 revoked) + 3 exchange requests

**To reset and re-seed:**
```bash
docker compose down -v          # wipes mongo_data volume
docker compose up -d
docker exec -it ehr_backend python seed.py
```

---

## Working with MongoDB Directly

```bash
# Open a MongoDB shell inside the container
docker exec -it ehr_mongodb mongosh ehrdb

# Useful mongosh commands:
show collections                    # list all collections
db.users.find().pretty()            # view all users
db.patients.count()                 # count patients
db.records.find({}, {title:1, accessPolicy:1})  # record metadata
db.audit_logs.find().sort({timestamp:-1}).limit(5)  # last 5 audit entries
db.revocation_list.find()           # who is revoked
exit
```

Or use **MongoDB Compass** (GUI):
- Connect to: `mongodb://localhost:27017`
- Database: `ehrdb`
- Collections: `users`, `patients`, `records`, `audit_logs`, `consents`, `hospitals`, `exchange_requests`, `revocation_list`

---

## Project Conventions

### Python (Backend)

```python
# Always use async/await for route handlers
@router.get("/patients")
async def list_patients(db = Depends(get_database)):
    ...

# Import collection names from database.py — never hardcode strings
from database import PATIENTS
docs = await db[PATIENTS].find(query).to_list(100)

# Always strip _id before building a Pydantic model from a MongoDB doc
doc.pop("_id", None)
patient = PatientResponse(**doc)

# Always call write_audit_log for write operations
from utils.audit_writer import write_audit_log
await write_audit_log(db=db, user=current_user, action=AuditAction.CREATE, ...)

# Use get_simulated_ip() for the ip_address parameter
from dependencies import get_simulated_ip
ip = get_simulated_ip()

# Use role_required as a route dependency, not inside the function body
@router.post("/records", dependencies=[Depends(role_required("doctor", "admin"))])
```

### TypeScript (Frontend)
- TypeScript strict mode ON — no `any` types
- All API calls via `src/api/client.ts` (once built) — never raw `fetch()`
- Auth state in Zustand store only — not component-local state
- Tailwind utility classes only — no inline `style={{}}` except for dynamic values

### Git

```bash
# Branch naming
feature/phase-4-frontend
feature/seed-script
fix/audit-verify-formula

# Commit messages
feat: implement GET /patients with soundex search
fix: recompute soundexCode when patient name is updated
docs: update BACKEND.md with Block 3 router details
```

---

## Environment Variables

All configured in `docker-compose.yml` for Docker, or in `backend/.env` for local dev:

| Variable | Docker default | Purpose |
|---|---|---|
| `MONGODB_URL` | `mongodb://mongodb:27017/ehrdb` | Database connection |
| `JWT_SECRET` | `ehr-super-secret-jwt-key-2024` | JWT signing — **change before sharing!** |
| `JWT_EXPIRE_HOURS` | `8` | Token lifetime in hours |
| `DEMO_ENCRYPTION_PASSWORD` | `EHR-DEMO-KEY-2024` | AES master key password |

Local dev `.env` (outside Docker):
```env
MONGODB_URL=mongodb://localhost:27017/ehrdb
JWT_SECRET=my-local-dev-secret
JWT_EXPIRE_HOURS=8
DEMO_ENCRYPTION_PASSWORD=EHR-DEMO-KEY-2024
```

---

## Troubleshooting

### Backend won't connect to MongoDB
```
RuntimeError: [DB] MongoDB ping failed
```
MongoDB takes ~15 seconds to fully start. The `healthcheck` in `docker-compose.yml` handles this, but if it still fails:
```bash
docker compose restart backend
```

### CP-ABE 403 on GET /records/{id}
You're getting this response:
```json
{"detail":"Access Denied","userAttributes":[...],"requiredPolicy":[...]}
```
Your user's `attributes` array doesn't satisfy the record's `accessPolicy`.
Fix: either update the user's attributes, or update the record's accessPolicy to match.

### Audit chain verify fails (intact: false)
Someone modified a log entry in MongoDB directly. The `brokenAt` field tells you which entry ID broke the chain. Don't do this — audit logs must be append-only.

### Port already in use
```
Error: port 8000 already in use
```
Change the host port in `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"   # use 8001 on your machine
```

### TypeScript errors in VS Code but app runs
```bash
# Ctrl+Shift+P → "TypeScript: Restart TS Server"
```

### Frontend shows old code after a change
Hard refresh: `Ctrl + Shift + R` in Chrome/Edge, or:
```bash
docker compose restart frontend
```

---

## VS Code Extensions

Add `.vscode/extensions.json` (already in the repo) — VS Code will recommend:

| Extension | Purpose |
|---|---|
| `ms-python.python` | Python language support |
| `ms-python.vscode-pylance` | Python type checking |
| `dbaeumer.vscode-eslint` | ESLint for TypeScript |
| `esbenp.prettier-vscode` | Code formatting |
| `bradlc.vscode-tailwindcss` | Tailwind CSS IntelliSense |
| `mongodb.mongodb-vscode` | MongoDB explorer + queries |
| `ms-azuretools.vscode-docker` | Docker Compose management |
| `yzhang.markdown-all-in-one` | Preview + formatting for docs |
