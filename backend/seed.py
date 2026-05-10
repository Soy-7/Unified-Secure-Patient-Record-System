"""
seed.py — One-time database population script for the EHR Platform demo.

Run with:
    python seed.py               (inside Docker: docker exec -it ehr_backend python seed.py)

Idempotent: if hospitals collection is not empty, the script exits without writing anything.
All passwords: Password@123
"""

import asyncio
import base64
import json
import uuid
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorClient

from config import settings
from crypto.aes import derive_key_from_password
from crypto.aes import encrypt as aes_encrypt
from crypto.ecdh import generate_keypair
from crypto.hashing import AUDIT_GENESIS_HASH, compute_audit_hash, hash_password
from crypto.soundex import soundex

# ---------------------------------------------------------------------------
# Encryption key (same static salt as records.py)
# HARDCODE: static salt — see SECURITY.md for production change
# ---------------------------------------------------------------------------
DEMO_SALT = b"EHR-SALT-2024-STATIC"
DEMO_KEY = derive_key_from_password(settings.demo_encryption_password, DEMO_SALT)
DEMO_PASSWORD_HASH = hash_password("Password@123")

# ---------------------------------------------------------------------------
# Pre-defined IDs (stable across re-seeds, easy to reference in docs/tests)
# ---------------------------------------------------------------------------
UID_SUPERADMIN  = "user-001"
UID_ADMIN       = "user-002"
UID_DR_PRIYA    = "user-003"
UID_NURSE       = "user-004"
UID_DR_VIKRAM   = "user-005"
UID_PATIENT_SR  = "user-006"

PID_SRIHARI  = str(uuid.uuid4())
PID_MEENA    = str(uuid.uuid4())
PID_ARJUN    = str(uuid.uuid4())
PID_LAKSHMI  = str(uuid.uuid4())
PID_RAJESH   = str(uuid.uuid4())
PID_PREETHI  = str(uuid.uuid4())
PID_KARTHIK  = str(uuid.uuid4())
PID_DIVYA    = str(uuid.uuid4())

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def days_ago(n: int, extra_hours: int = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=n, hours=extra_hours)
    return dt.isoformat()

def encrypt_record(content: dict) -> tuple[str, str]:
    """Encrypt a dict as JSON. Returns (encryptedContent_b64, iv_b64)."""
    enc = aes_encrypt(json.dumps(content), DEMO_KEY)
    ct  = base64.b64decode(enc["ciphertext"])
    tag = base64.b64decode(enc["tag"])
    combined = base64.b64encode(ct + tag).decode("utf-8")
    return combined, enc["iv"]

def make_audit_entry(
    entry_id: str,
    user_id: str,
    user_name: str,
    user_role: str,
    action: str,
    resource_type: str,
    resource_id: str,
    hospital_id: str,
    ip: str,
    timestamp: str,
    details: str,
    prev_hash: str,
) -> dict:
    entry_data = f"{user_id}{action}{resource_type}{resource_id}{timestamp}{details}"
    entry_hash = compute_audit_hash(prev_hash, entry_data)
    return {
        "id": entry_id, "userId": user_id, "userName": user_name,
        "userRole": user_role, "action": action, "resourceType": resource_type,
        "resourceId": resource_id, "hospitalId": hospital_id,
        "ipAddress": ip, "timestamp": timestamp,
        "hash": entry_hash, "prevHash": prev_hash, "details": details,
    }

# ---------------------------------------------------------------------------
# Data builders
# ---------------------------------------------------------------------------

def build_hospitals() -> list[dict]:
    now = now_iso()
    return [
        {"id": "hosp-001", "name": "City General Hospital",  "city": "Chennai",
         "apiEndpoint": "https://api.citygeneral.in/ehr",
         "tlsCertFingerprint": "SHA256:4A:B2:C3:D4:E5:F6:A7:B8:C9:D0:E1:F2:A3:B4:C5:D6:E7:F8:A9:B0",
         "createdAt": now},
        {"id": "hosp-002", "name": "Apollo Medical Center",  "city": "Chennai",
         "apiEndpoint": "https://api.apollo.in/ehr",
         "tlsCertFingerprint": "SHA256:7C:F1:A2:B3:C4:D5:E6:F7:A8:B9:C0:D1:E2:F3:A4:B5:C6:D7:E8:F9",
         "createdAt": now},
        {"id": "hosp-003", "name": "AIIMS Regional",         "city": "Delhi",
         "apiEndpoint": "https://api.aiims.in/ehr",
         "tlsCertFingerprint": "SHA256:2E:A9:B1:C2:D3:E4:F5:A6:B7:C8:D9:E0:F1:A2:B3:C4:D5:E6:F7:A8",
         "createdAt": now},
    ]


def build_users() -> list[dict]:
    now = now_iso()
    users_raw = [
        (UID_SUPERADMIN, "Super Admin",       "superadmin@ehr.in",          "admin",   "hosp-001", ["admin", "superadmin"],      "Administration"),
        (UID_ADMIN,      "Admin Ramesh K.",    "admin@citygeneral.in",        "admin",   "hosp-001", ["admin"],                    "Administration"),
        ("user-007",     "City Hospital",     "hospital@hospital.in",        "admin",   "hosp-001", ["admin", "nurse"],           "Front Desk"),
        (UID_DR_PRIYA,   "Dr. Priya Sharma",  "dr.priya@citygeneral.in",     "doctor",  "hosp-001", ["doctor", "cardiology", "senior"], "Cardiology"),
        (UID_NURSE,      "Nurse Anitha R.",   "nurse.anitha@citygeneral.in", "nurse",   "hosp-001", ["nurse", "general"],         "General Ward"),
        (UID_DR_VIKRAM,  "Dr. Vikram Nair",   "dr.vikram@apollo.in",         "doctor",  "hosp-002", ["doctor", "neurology"],      "Neurology"),
        (UID_PATIENT_SR, "Srihari P.",        "srihari@patient.in",          "patient", "hosp-001", ["patient"],                  None),
    ]
    docs = []
    for uid, name, email, role, hosp, attrs, dept in users_raw:
        keys = generate_keypair()
        docs.append({
            "id": uid, "name": name, "email": email,
            "passwordHash": DEMO_PASSWORD_HASH,
            "role": role, "hospitalId": hosp,
            "department": dept, "attributes": attrs,
            "publicKey": keys["publicKey"], "privateKey": keys["privateKey"],
            "createdAt": now, "isRevoked": False,
        })
    return docs


def build_patients() -> list[dict]:
    now = now_iso()
    raw = [
        (PID_SRIHARI, "Srihari Prabhu",      "1990-05-14", "Male",   "B+",  "9841023456", "hosp-001", ["hosp-002"]),
        (PID_MEENA,   "Meena Krishnamurthy",  "1985-11-22", "Female", "O+",  "9840134567", "hosp-001", []),
        (PID_ARJUN,   "Arjun Venkatesh",      "1978-03-07", "Male",   "A+",  "9787654321", "hosp-002", ["hosp-001"]),
        (PID_LAKSHMI, "Lakshmi Devi",         "1995-08-19", "Female", "AB+", "9976543210", "hosp-001", []),
        (PID_RAJESH,  "Rajesh Kumar",         "1970-12-01", "Male",   "O-",  "9865432109", "hosp-003", ["hosp-001"]),
        (PID_PREETHI, "Preethi Subramaniam",  "2000-06-30", "Female", "A-",  "9754321098", "hosp-002", []),
        (PID_KARTHIK, "Karthik Sundaram",     "1988-09-15", "Male",   "B-",  "9643210987", "hosp-001", ["hosp-003"]),
        (PID_DIVYA,   "Divya Natarajan",      "1993-02-28", "Female", "AB-", "9532109876", "hosp-003", []),
    ]
    docs = []
    for pid, name, dob, gender, bg, phone, hosp, linked in raw:
        docs.append({
            "id": pid, "soundexCode": soundex(name),
            "name": name, "dob": dob, "gender": gender,
            "bloodGroup": bg, "phone": phone, "email": None,
            "address": "Chennai, Tamil Nadu",
            "primaryHospitalId": hosp, "linkedHospitalIds": linked,
            "emergencyContact": {"name": "Family Member", "relation": "spouse", "phone": "9999999999"},
            "createdAt": now, "updatedAt": now,
        })
    return docs


def build_records(patients: list[dict]) -> list[dict]:
    now = now_iso()
    conditions = ["Hypertension", "Type 2 Diabetes", "Migraine", "Asthma",
                  "Hypothyroidism", "Anemia", "Gastritis", "Dengue Fever"]
    drugs      = ["Amlodipine", "Metformin", "Sumatriptan", "Salbutamol",
                  "Levothyroxine", "Iron Supplement", "Pantoprazole", "Paracetamol"]

    # createdBy: hosp-002 patients → dr_vikram, everything else → dr_priya
    def creator(hosp: str) -> str:
        return UID_DR_VIKRAM if hosp == "hosp-002" else UID_DR_PRIYA

    docs = []
    for i, p in enumerate(patients):
        cond = conditions[i]
        drug = drugs[i]
        hosp = p["primaryHospitalId"]
        pid  = p["id"]
        by   = creator(hosp)

        # Record 1 — diagnosis
        c1, iv1 = encrypt_record({
            "diagnosis": cond, "symptoms": ["fatigue", "headache"],
            "severity": "moderate", "notes": "Patient presented with classic symptoms.",
            "followUp": "2 weeks",
        })
        docs.append({
            "id": str(uuid.uuid4()), "patientId": pid, "hospitalId": hosp,
            "createdBy": by, "recordType": "diagnosis",
            "title": f"Initial Diagnosis — {cond}",
            "encryptedContent": c1, "iv": iv1,
            "accessPolicy": ["doctor"], "tags": [cond.lower().replace(" ", "-")],
            "createdAt": now, "updatedAt": now, "isFlagged": False,
        })

        # Record 2 — prescription
        c2, iv2 = encrypt_record({
            "medications": [{"name": drug, "dosage": "500mg",
                             "frequency": "twice daily", "duration": "7 days"}],
            "prescribedBy": "Dr. Priya Sharma", "warnings": ["Take with food"],
        })
        docs.append({
            "id": str(uuid.uuid4()), "patientId": pid, "hospitalId": hosp,
            "createdBy": by, "recordType": "prescription",
            "title": f"Prescription — {drug}",
            "encryptedContent": c2, "iv": iv2,
            "accessPolicy": ["doctor", "nurse"], "tags": ["medication"],
            "createdAt": now, "updatedAt": now, "isFlagged": False,
        })

        # Record 3 — lab_result
        c3, iv3 = encrypt_record({
            "tests": [
                {"name": "Hemoglobin", "value": "13.5", "unit": "g/dL", "normalRange": "12-17"},
                {"name": "WBC", "value": "7200", "unit": "cells/μL", "normalRange": "4500-11000"},
            ],
            "labTechnician": "Lab Tech Suresh", "reportDate": now[:10],
        })
        docs.append({
            "id": str(uuid.uuid4()), "patientId": pid, "hospitalId": hosp,
            "createdBy": by, "recordType": "lab_result",
            "title": "Lab Results — CBC",
            "encryptedContent": c3, "iv": iv3,
            "accessPolicy": ["doctor", "nurse"], "tags": ["lab", "cbc"],
            "createdAt": now, "updatedAt": now, "isFlagged": False,
        })

        # Record 4 — consultation
        c4, iv4 = encrypt_record({
            "specialist": "Dr. Vikram Nair", "specialty": "Neurology",
            "findings": "No acute neurological deficit",
            "recommendations": "MRI Brain advised", "urgency": "routine",
        })
        docs.append({
            "id": str(uuid.uuid4()), "patientId": pid, "hospitalId": hosp,
            "createdBy": by, "recordType": "consultation",
            "title": "Specialist Consultation",
            "encryptedContent": c4, "iv": iv4,
            "accessPolicy": ["doctor", "cardiology"], "tags": ["specialist"],
            "createdAt": now, "updatedAt": now, "isFlagged": False,
        })

    return docs


def build_audit_logs() -> list[dict]:
    """
    25 chained log entries with realistic timestamps over 7 days.
    Chain starts with AUDIT_GENESIS_HASH ("0" * 64).
    """
    IPS = ["192.168.1.45", "192.168.2.112", "192.168.3.87"]

    # Each tuple: (user_id, user_name, user_role, action, resource_type, resource_id, hospital_id, ip_idx, days_ago_offset, hours_offset, details)
    entries_spec = [
        # Day 7 — superadmin and admin session
        (UID_SUPERADMIN, "Super Admin",      "admin",  "LOGIN",         "system",  "system",    "hosp-001", 0, 7, 9,  "Super Admin logged in"),
        (UID_ADMIN,      "Admin Ramesh K.",  "admin",  "LOGIN",         "system",  "system",    "hosp-001", 1, 7, 9.5,"Admin Ramesh K. logged in"),
        (UID_ADMIN,      "Admin Ramesh K.",  "admin",  "CREATE",        "patient", PID_SRIHARI, "hosp-001", 1, 7, 10, "Created patient 'Srihari Prabhu'"),
        (UID_ADMIN,      "Admin Ramesh K.",  "admin",  "CREATE",        "patient", PID_MEENA,   "hosp-001", 1, 7, 10.5,"Created patient 'Meena Krishnamurthy'"),
        (UID_ADMIN,      "Admin Ramesh K.",  "admin",  "LOGOUT",        "system",  "system",    "hosp-001", 1, 7, 11, "Admin Ramesh K. logged out"),
        # Day 6 — Dr. Priya session
        (UID_DR_PRIYA,   "Dr. Priya Sharma","doctor", "LOGIN",         "system",  "system",    "hosp-001", 2, 6, 9,  "Dr. Priya Sharma logged in"),
        (UID_DR_PRIYA,   "Dr. Priya Sharma","doctor", "VIEW",          "patient", PID_SRIHARI, "hosp-001", 2, 6, 9.5,"Viewed patient 'Srihari Prabhu'"),
        (UID_DR_PRIYA,   "Dr. Priya Sharma","doctor", "CREATE",        "record",  "rec-demo-1","hosp-001", 2, 6, 10, "Created diagnosis record for Srihari"),
        (UID_DR_PRIYA,   "Dr. Priya Sharma","doctor", "VIEW",          "record",  "rec-demo-1","hosp-001", 2, 6, 10.3,"Viewed and decrypted diagnosis record"),
        (UID_DR_PRIYA,   "Dr. Priya Sharma","doctor", "LOGOUT",        "system",  "system",    "hosp-001", 2, 6, 11, "Dr. Priya Sharma logged out"),
        # Day 5 — Nurse session + access denied
        (UID_NURSE,      "Nurse Anitha R.", "nurse",  "LOGIN",         "system",  "system",    "hosp-001", 0, 5, 8,  "Nurse Anitha R. logged in"),
        (UID_NURSE,      "Nurse Anitha R.", "nurse",  "VIEW",          "record",  "rec-demo-2","hosp-001", 0, 5, 8.5,"Viewed prescription record"),
        (UID_NURSE,      "Nurse Anitha R.", "nurse",  "ACCESS_DENIED", "record",  "rec-demo-1","hosp-001", 0, 5, 9,  "Access denied: attributes ['nurse','general'] did not satisfy policy ['doctor']"),
        (UID_NURSE,      "Nurse Anitha R.", "nurse",  "LOGOUT",        "system",  "system",    "hosp-001", 0, 5, 9.5,"Nurse Anitha R. logged out"),
        # Day 4 — Dr. Vikram session
        (UID_DR_VIKRAM,  "Dr. Vikram Nair", "doctor", "LOGIN",         "system",  "system",    "hosp-002", 2, 4, 10, "Dr. Vikram Nair logged in"),
        (UID_DR_VIKRAM,  "Dr. Vikram Nair", "doctor", "VIEW",          "patient", PID_ARJUN,   "hosp-002", 2, 4, 10.5,"Viewed patient 'Arjun Venkatesh'"),
        (UID_DR_VIKRAM,  "Dr. Vikram Nair", "doctor", "VIEW",          "record",  "rec-demo-3","hosp-002", 2, 4, 11, "Viewed lab result record"),
        (UID_DR_VIKRAM,  "Dr. Vikram Nair", "doctor", "CREATE",        "record",  "rec-demo-4","hosp-002", 2, 4, 11.5,"Created consultation record for Arjun"),
        (UID_DR_PRIYA,   "Dr. Priya Sharma","doctor", "SHARE",         "patient", PID_SRIHARI, "hosp-001", 1, 4, 14, "Consent granted to dr.vikram for patient Srihari"),
        (UID_DR_VIKRAM,  "Dr. Vikram Nair", "doctor", "LOGOUT",        "system",  "system",    "hosp-002", 2, 4, 15, "Dr. Vikram Nair logged out"),
        # Day 3 — Superadmin session
        (UID_SUPERADMIN, "Super Admin",      "admin",  "LOGIN",         "system",  "system",    "hosp-001", 0, 3, 9,  "Super Admin logged in"),
        (UID_SUPERADMIN, "Super Admin",      "admin",  "VIEW",          "patient", PID_RAJESH,  "hosp-001", 0, 3, 9.5,"Viewed patient 'Rajesh Kumar'"),
        (UID_SUPERADMIN, "Super Admin",      "admin",  "CREATE",        "patient", PID_KARTHIK, "hosp-001", 0, 3, 10, "Created patient 'Karthik Sundaram'"),
        (UID_NURSE,      "Nurse Anitha R.", "nurse",  "ACCESS_DENIED", "record",  "rec-demo-4","hosp-001", 0, 3, 11, "Access denied: attributes ['nurse','general'] did not satisfy policy ['doctor','cardiology']"),
        (UID_SUPERADMIN, "Super Admin",      "admin",  "LOGOUT",        "system",  "system",    "hosp-001", 0, 3, 12, "Super Admin logged out"),
    ]

    logs = []
    prev_hash = AUDIT_GENESIS_HASH

    for spec in entries_spec:
        uid, uname, urole, action, res_type, res_id, hosp, ip_i, dago, hago, details = spec
        # Convert fractional hours to integer minutes for timedelta
        total_hours = int(hago)
        extra_mins  = int((hago - total_hours) * 60)
        ts = (
            datetime.now(timezone.utc)
            - timedelta(days=dago, hours=total_hours, minutes=extra_mins)
        ).isoformat()

        entry = make_audit_entry(
            entry_id=str(uuid.uuid4()),
            user_id=uid, user_name=uname, user_role=urole,
            action=action, resource_type=res_type,
            resource_id=res_id, hospital_id=hosp,
            ip=IPS[ip_i], timestamp=ts, details=details,
            prev_hash=prev_hash,
        )
        prev_hash = entry["hash"]
        logs.append(entry)

    return logs


def build_consents() -> list[dict]:
    now = now_iso()
    today    = datetime.now(timezone.utc)
    in30     = (today + timedelta(days=30)).isoformat()
    in60     = (today + timedelta(days=60)).isoformat()
    yesterday = (today - timedelta(days=1)).isoformat()

    return [
        {
            "id": str(uuid.uuid4()), "patientId": PID_SRIHARI,
            "grantedTo": UID_DR_VIKRAM, "grantedToType": "user",
            "recordIds": ["*"], "permissions": ["read"],
            "validFrom": now, "validUntil": in30,
            "isRevoked": False, "revokedAt": None, "createdAt": now,
        },
        {
            "id": str(uuid.uuid4()), "patientId": PID_MEENA,
            "grantedTo": "hosp-002", "grantedToType": "hospital",
            "recordIds": ["*"], "permissions": ["read", "share"],
            "validFrom": now, "validUntil": in60,
            "isRevoked": False, "revokedAt": None, "createdAt": now,
        },
        {
            "id": str(uuid.uuid4()), "patientId": PID_ARJUN,
            "grantedTo": UID_DR_PRIYA, "grantedToType": "user",
            "recordIds": ["*"], "permissions": ["read"],
            "validFrom": now, "validUntil": in30,
            "isRevoked": False, "revokedAt": None, "createdAt": now,
        },
        {
            "id": str(uuid.uuid4()), "patientId": PID_RAJESH,
            "grantedTo": "hosp-002", "grantedToType": "hospital",
            "recordIds": ["*"], "permissions": ["read"],
            "validFrom": now, "validUntil": in30,
            "isRevoked": True, "revokedAt": yesterday, "createdAt": now,
        },
    ]


def build_exchange_requests() -> list[dict]:
    now = now_iso()
    return [
        {
            "id": str(uuid.uuid4()),
            "fromHospitalId": "hosp-001", "toHospitalId": "hosp-002",
            "patientId": PID_SRIHARI, "requestedBy": UID_DR_PRIYA,
            "status": "pending",
            "recordTypes": ["diagnosis", "lab_result"],
            "purpose": "Cardiology referral for specialist opinion",
            "encryptedPayload": None, "createdAt": now, "resolvedAt": None,
        },
        {
            "id": str(uuid.uuid4()),
            "fromHospitalId": "hosp-002", "toHospitalId": "hosp-001",
            "patientId": PID_ARJUN, "requestedBy": UID_DR_VIKRAM,
            "status": "completed",
            "recordTypes": ["*"],
            "purpose": "Transfer of care — patient relocated",
            "encryptedPayload": "ZGVtby1wYXlsb2Fk",  # placeholder base64
            "createdAt": days_ago(5), "resolvedAt": days_ago(4),
        },
        {
            "id": str(uuid.uuid4()),
            "fromHospitalId": "hosp-001", "toHospitalId": "hosp-003",
            "patientId": PID_RAJESH, "requestedBy": UID_DR_PRIYA,
            "status": "approved",
            "recordTypes": ["consultation", "imaging"],
            "purpose": "Specialist consultation request",
            "encryptedPayload": None, "createdAt": days_ago(2), "resolvedAt": days_ago(1),
        },
    ]


# ---------------------------------------------------------------------------
# Main seeder
# ---------------------------------------------------------------------------

async def main() -> None:
    client = AsyncIOMotorClient(settings.mongodb_url)
    db     = client.get_default_database()

    print(f"[seed] Connecting to {settings.mongodb_url} ...")

    # Idempotency check
    count = await db["hospitals"].count_documents({})
    if count > 0:
        print("[seed] DB already seeded, skipping.")
        client.close()
        return

    # 1. Hospitals
    print("[seed] Seeding hospitals...")
    hospitals = build_hospitals()
    await db["hospitals"].insert_many(hospitals)

    # 2. Users
    print("[seed] Seeding users...")
    users = build_users()
    await db["users"].insert_many(users)

    # 3. Patients
    print("[seed] Seeding patients...")
    patients = build_patients()
    await db["patients"].insert_many(patients)

    # 4. EHR Records
    print("[seed] Seeding EHR records (encrypting 32 records)...")
    records = build_records(patients)
    await db["records"].insert_many(records)

    # 5. Audit Logs
    print("[seed] Seeding audit logs (building hash chain for 25 entries)...")
    audit_logs = build_audit_logs()
    await db["audit_logs"].insert_many(audit_logs)

    # 6. Consents
    print("[seed] Seeding consents...")
    consents = build_consents()
    await db["consents"].insert_many(consents)

    # 7. Exchange Requests
    print("[seed] Seeding exchange requests...")
    exchanges = build_exchange_requests()
    await db["exchange_requests"].insert_many(exchanges)

    client.close()

    print("""
Seeding complete.
  Hospitals:          3
  Users:              6
  Patients:           8
  EHR Records:       32
  Audit Log Entries: 25
  Consents:           4
  Exchange Requests:  3

Demo credentials — all passwords: Password@123
  superadmin@ehr.in          (Super Admin)
  admin@citygeneral.in       (Admin)
  dr.priya@citygeneral.in    (Doctor — City General)
  nurse.anitha@citygeneral.in (Nurse)
  dr.vikram@apollo.in        (Doctor — Apollo)
  srihari@patient.in         (Patient)
""")


if __name__ == "__main__":
    asyncio.run(main())
