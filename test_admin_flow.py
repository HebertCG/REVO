import requests, json

# Login admin
res = requests.post("http://localhost:8011/auth/login", json={"email":"admin@revo.edu","password":"Admin@REVO2025"})
print("Login status:", res.status_code)
if res.status_code != 200:
    print("ERROR:", res.text)
    exit()

token = res.json()["access_token"]
print("Token ok:", token[:40], "...")

# Decode middle part to see role
import base64
payload_b64 = token.split(".")[1]
padding = 4 - len(payload_b64) % 4
payload_b64 += "=" * padding
decoded = json.loads(base64.b64decode(payload_b64))
print("JWT payload:", decoded)

# Test retrain
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
res2 = requests.post("http://localhost:8013/stats/train", json={}, headers=headers)
print("Retrain status:", res2.status_code)
print("Retrain body:", res2.text[:300])
