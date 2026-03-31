import urllib.request
import urllib.error
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE_AUTH = "http://localhost:8011/auth"
BASE_SURVEY = "http://localhost:8012"
BASE_ML = "http://localhost:8013/predict"

def fetch(url, method="GET", json_data=None, headers=None):
    if headers is None: headers = {}
    data = None
    if json_data is not None:
        data = json.dumps(json_data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, context=ctx) as r:
            res_body = r.read().decode("utf-8")
            return r.status, json.loads(res_body) if res_body else {}
    except urllib.error.HTTPError as e:
        res_body = e.read().decode("utf-8")
        return e.code, json.loads(res_body) if res_body else str(e)
    except Exception as e:
        return 0, str(e)

print("1. Login demo@revo.edu")
status, res = fetch(f"{BASE_AUTH}/login", "POST", {"email": "demo@revo.edu", "password": "Demo@1234"})
token = res.get("access_token")
headers = {"Authorization": f"Bearer {token}"}
user_id = res.get("user", {}).get("id")
print("User ID:", user_id)

print("\n2. Create session")
status, res = fetch(f"{BASE_SURVEY}/sessions/", "POST", {}, headers)
if status != 201:
    print("Failed finding session result:", status, res)
    exit(1)
session_id = res["id"]
print("Session ID:", session_id)

print("\n3. Get Questions")
status, questions = fetch(f"{BASE_SURVEY}/questions/")

print("\n4. Submit bulk answers")
answers = [{"question_id": q["id"], "value": 4} for q in questions]
status, res = fetch(f"{BASE_SURVEY}/sessions/{session_id}/answers", "POST", {"answers": answers}, headers)
print("Submit answers status:", status)
if status != 200:
    print("Error:", res)

print("\n5. Complete session")
status, res = fetch(f"{BASE_SURVEY}/sessions/{session_id}/complete", "POST", {}, headers)
print("Complete session status:", status)
if status != 200:
    print("Error:", res)
else:
    feature_vector = res.get("feature_vector")
    print("\n6. Predict with ML service")
    status, res = fetch(f"{BASE_ML}/", "POST", {
        "session_id": session_id,
        "user_id": user_id,
        "feature_vector": feature_vector
    }, headers)
    print("Predict status:", status)
    print("Predict Response:", res)
