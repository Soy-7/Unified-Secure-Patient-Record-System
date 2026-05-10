import requests
import json

base_url = "http://localhost:8000"

# 1. Login as patient
login_data = {
    "username": "srihari@patient.in",
    "password": "Password@123" # Default demo password
}
resp = requests.post(f"{base_url}/auth/login", data=login_data)
print("Login Response:", resp.text)
token = resp.json().get("access_token")
print("Token:", token)

headers = {"Authorization": f"Bearer {token}"}

# 2. Get patient ID
p_resp = requests.get(f"{base_url}/patients?search=Srihari", headers=headers)
patient_id = p_resp.json()["patients"][0]["id"]
print("Patient ID:", patient_id)

# 3. Post a record
record_data = {
    "patientId": patient_id,
    "hospitalId": "patient-upload",
    "recordType": "diagnosis",
    "title": "Test Upload",
    "content": '{"text": "test", "fileName": "test.txt", "fileData": ""}',
    "accessPolicy": ["patient"],
    "tags": ["patient_uploaded"]
}
resp = requests.post(f"{base_url}/records", json=record_data, headers=headers)
print("Post Record Status:", resp.status_code)
print("Response:", resp.text)
