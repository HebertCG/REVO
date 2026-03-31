import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Re-login to get token
req1 = urllib.request.Request("http://localhost:8011/auth/login", method="POST", data=b'{"email": "demo@revo.edu", "password": "Demo@1234"}', headers={"Content-Type": "application/json"})
res1 = json.loads(urllib.request.urlopen(req1, context=ctx).read())
token = res1["access_token"]
user_id = res1["user"]["id"]

data = {
    "session_id": 22,
    "user_id": user_id,
    "feature_vector": {f"q{i}": 4 for i in range(1, 21)}
}

req = urllib.request.Request("http://localhost:8013/predict/", method="POST", headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}, data=json.dumps(data).encode("utf-8"))

try:
    print("Sending predict request...")
    with urllib.request.urlopen(req, context=ctx) as r:
        print("Success:", r.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}:")
    print(e.read().decode("utf-8"))
except Exception as e:
    print("Other error:", e)
