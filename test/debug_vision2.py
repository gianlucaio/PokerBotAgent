import requests
import json
import base64
import os

url = "http://localhost:1234/v1/chat/completions"

# Prova con primo screenshot
shots_dir = os.path.join(os.path.dirname(__file__), "..", "modalità-web-9max-2colori")
shots = [f for f in os.listdir(shots_dir) if f.endswith('.png')]
if shots:
    shot_path = os.path.join(shots_dir, shots[0])
    print(f"Testing with: {shots[0]}")
    with open(shot_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    payload = {
        "model": "qwen3-vl-8b-instruct",
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": "What do you see in this poker screenshot?"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
            ]}
        ],
        "temperature": 0.0,
        "max_tokens": 200
    }

    try:
        response = requests.post(url, json=payload, timeout=60)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(response.json())
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")