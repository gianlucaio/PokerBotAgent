import requests
import json

url = "http://localhost:1234/v1/chat/completions"
payload = {
    "model": "qwen3-vl-8b-instruct",
    "messages": [
        {"role": "user", "content": "Test"}
    ]
}

try:
    response = requests.post(url, json=payload)
    print(f"Status: {response.status_code}")
    print(response.json())
except Exception as e:
    print(f"Error: {e}")
