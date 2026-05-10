import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings

async def fix_db():
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client["ehrdb"]
    # Update the patient to have the correct email
    await db["patients"].update_one(
        {"name": "Srihari Prabhu"},
        {"$set": {"email": "srihari@patient.in"}}
    )
    print("Fixed patient email in DB!")

asyncio.run(fix_db())
