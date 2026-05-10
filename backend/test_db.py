import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings

async def query():
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client["ehrdb"]
    pats = await db["patients"].find().to_list(length=10)
    print("All patients:", pats)

asyncio.run(query())
