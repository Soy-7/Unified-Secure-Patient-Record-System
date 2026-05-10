import asyncio
import json
import base64
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings
from crypto.aes import derive_key_from_password, encrypt

DEMO_SALT = b"EHR-SALT-2024-STATIC"
DEMO_KEY = derive_key_from_password(settings.demo_encryption_password, DEMO_SALT)

# A tiny valid PDF base64 string (literally just an empty PDF)
DUMMY_PDF_B64 = "data:application/pdf;base64,JVBERi0xLjQKMSAwIG9iago8PAovVHlwZSAvQ2F0YWxvZwovUGFnZXMgMiAwIFIKPj4KZW5kb2JqCjIgMCBvYmoKPDwKL1R5cGUgL1BhZ2VzCi9LaWRzIFszIDAgUl0KL0NvdW50IDEKPj4KZW5kb2JqCjMgMCBvYmoKPDwKL1R5cGUgL1BhZ2UKL1BhcmVudCAyIDAgUgovTWVkaWFCb3ggWzAgMCA1OTUuMjgxIDg0MS44OV0KPj4KZW5kb2JqCnhyZWYKMCA0CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDAwOSAwMDAwMCBuIAowMDAwMDAwMDUyIDAwMDAwIG4gCjAwMDAwMDAxMDQgMDAwMDAgbiAKdHJhaWxlcgo8PAovU2l6ZSA0Ci9Sb290IDEgMCBSCj4+CnN0YXJ0eHJlZgoxNzMKJSVFT0YK"

async def add_pdfs_to_records():
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client["ehrdb"]
    
    # Get all records
    records_cursor = db["records"].find()
    records = await records_cursor.to_list(length=100)
    
    count = 0
    for record in records:
        # We will append a dummy PDF to some records
        if count >= 10:
            break
            
        record_type = record.get("recordType", "document")
        file_name = f"dummy_{record_type}_{count}.pdf"
        
        # Create new plaintext content
        content_obj = {
            "text": f"This is an automatically generated {record_type} report with an attached PDF.",
            "fileName": file_name,
            "fileData": DUMMY_PDF_B64
        }
        plaintext = json.dumps(content_obj)
        
        # Encrypt
        enc_res = encrypt(plaintext, DEMO_KEY)
        
        # Update record in DB
        await db["records"].update_one(
            {"id": record["id"]},
            {"$set": {
                "encryptedContent": enc_res["ciphertext"],
                "iv": enc_res["iv"]
            }}
        )
        print(f"Updated record {record['id']} with a PDF attachment.")
        count += 1
        
    print(f"Successfully added PDFs to {count} records!")
    client.close()

if __name__ == "__main__":
    asyncio.run(add_pdfs_to_records())
