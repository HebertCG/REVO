import requests
try:
    print(requests.get('http://localhost:8012/health').json())
except Exception as e:
    print("Error:", e)
