import requests

login_data = {"email": "demo@revo.edu", "password": "Demo@1234"}
res_auth = requests.post("http://localhost:8011/auth/login", json=login_data)
token = res_auth.json().get("access_token")

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
body = {
    "session_id": 998,
    "user_id": 2,
    "feature_vector": {"aff_1":0.6,"aff_2":0.3,"aff_3":0.1,"aff_4":0.1,"aff_5":0.1,"aff_6":0.1,"aff_7":0.1,"aff_8":0.1,"aff_9":0.1,"aff_10":0.1}
}

res = requests.post("http://localhost:8013/predict/", json=body, headers=headers)
print("STATUS CODE:", res.status_code)
print("RESPONSE TEXT:", res.text)
