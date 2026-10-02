"""
test_login.py — Prueba login y registro directamente via HTTP
"""
import urllib.request
import urllib.error
import json

BASE = "http://localhost:8011"

def post_json(url, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 0, str(e)

print("=== TEST 1: Login demo ===")
code, resp = post_json(f"{BASE}/auth/login", {"email":"demo@revo.edu","password":"Demo@1234"})
print(f"Status: {code}")
if code == 200:
    print(f"Token: {resp['access_token'][:40]}...")
    print(f"User: {resp['user']['full_name']} | Role: {resp['user']['role']}")
else:
    print(f"Error: {resp}")

print("\n=== TEST 2: Registro nuevo usuario ===")
code2, resp2 = post_json(f"{BASE}/auth/register", {
    "email": "carlos.test@universidad.edu",
    "password": "Test@1234",
    "full_name": "Carlos Test",
    "student_code": "SIS-2026-TEST",
    "semester": 5
})
print(f"Status: {code2}")
if code2 == 201:
    print(f"OK! Token: {resp2['access_token'][:40]}...")
    print(f"User: {resp2['user']['full_name']} | ID: {resp2['user']['id']}")
else:
    print(f"Respuesta: {resp2}")
