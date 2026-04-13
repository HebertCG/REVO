"""
Test login directo usando el cliente HTTP integrado de FastAPI (TestClient)
para capturar el traceback completo del 500 sin necesidad de requests externo.
"""
import sys
sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from main import app

client = TestClient(app, raise_server_exceptions=True)

try:
    r = client.post("/auth/login", json={"email": "admin@revo.edu", "password": "Admin@REVO2025"})
    print("Status:", r.status_code)
    print("Body:", r.text[:600])
except Exception as e:
    import traceback
    traceback.print_exc()
