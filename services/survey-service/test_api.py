import requests
import json

# Log in first to get token
r1 = requests.post("http://localhost:8011/auth/login", json={"email": "h.cornejo1@gmail.com", "password": "secure_password"})
if r1.status_code != 200:
    print("Login failed:", r1.text)
else:
    token = r1.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # create session
    r2 = requests.post("http://localhost:8012/sessions/", headers=headers)
    print("Create session:", r2.status_code, r2.text)
    
    sid = r2.json()["id"]
    
    # get questions
    r3 = requests.get(f"http://localhost:8012/sessions/{sid}/questions", headers=headers)
    print("Questions:", r3.status_code)
    print("Data:", r3.json())
