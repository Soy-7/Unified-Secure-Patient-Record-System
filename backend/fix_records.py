import asyncio
import base64
import json
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings
from crypto.aes import derive_key_from_password, encrypt

DEMO_SALT = b"EHR-SALT-2024-STATIC"
DEMO_KEY = derive_key_from_password(settings.demo_encryption_password, DEMO_SALT)

DUMMY_PDF_B64 = "data:application/pdf;base64,JVBERi0xLjQKMSAwIG9iago8PAovVHlwZSAvQ2F0YWxvZwovUGFnZXMgMiAwIFIKPj4KZW5kb2JqCjIgMCBvYmoKPDwKL1R5cGUgL1BhZ2VzCi9LaWRzIFszIDAgUl0KL0NvdW50IDEKPj4KZW5kb2JqCjMgMCBvYmoKPDwKL1R5cGUgL1BhZ2UKL1BhcmVudCAyIDAgUgovTWVkaWFCb3ggWzAgMCA1OTUuMjgxIDg0MS44OV0KPj4KZW5kb2JqCnhyZWYKMCA0CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDAwOSAwMDAwMCBuIAowMDAwMDAwMDUyIDAwMDAwIG4gCjAwMDAwMDAxMDQgMDAwMDAgbiAKdHJhaWxlcgo8PAovU2l6ZSA0Ci9Sb290IDEgMCBSCj4+CnN0YXJ0eHJlZgoxNzMKJSVFT0YK"

async def fix_records():
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client["ehrdb"]
    
    records = await db["records"].find().to_list(length=100)
    for r in records:
        record_type = r.get("recordType", "document")
        content_obj = {
            "text": f"This is an automatically generated {record_type} report with an attached PDF.",
            "fileName": f"dummy_{record_type}.pdf",
            "fileData": DUMMY_PDF_B64
        }
        plaintext = json.dumps(content_obj)
        enc_res = encrypt(plaintext, DEMO_KEY)
        
        ct_bytes  = base64.b64decode(enc_res["ciphertext"])
        tag_bytes = base64.b64decode(enc_res["tag"])
        encrypted_content = base64.b64encode(ct_bytes + tag_bytes).decode("utf-8")
        
        await db["records"].update_one(
            {"id": r["id"]},
            {"$set": {
                "encryptedContent": encrypted_content,
                "iv": enc_res["iv"]
            }}
        )
    print("Fixed all records!")

if __name__ == "__main__":
    asyncio.run(fix_records())
