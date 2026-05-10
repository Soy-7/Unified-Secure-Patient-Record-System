import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings
from crypto.ecdh import generate_keypair
from crypto.hashing import hash_password
from datetime import datetime, timezone

async def add_hospital():
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client["ehrdb"]
    keys = generate_keypair()
    now = datetime.now(timezone.utc).isoformat()
    
    # Insert hospital user
    await db["users"].insert_one({
        "id": "user-hospital",
        "name": "City Hospital Front Desk",
        "email": "hospital@hospital.in",
        "passwordHash": hash_password("Password@123"),
        "role": "admin",
        "hospitalId": "hosp-001",
        "department": "Front Desk",
        "attributes": ["admin", "nurse"],
        "publicKey": keys["publicKey"],
        "privateKey": keys["privateKey"],
        "createdAt": now,
        "isRevoked": False,
    })
    print("Hospital account added successfully!")

asyncio.run(add_hospital())
