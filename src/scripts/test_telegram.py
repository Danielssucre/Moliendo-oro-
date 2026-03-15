import requests
import json
import os

# Mocking config to get actual tokens
config_path = "/Users/danielsuarezsucre/TRADING/trading_agent/config/config.json"
with open(config_path, "r") as f:
    config_data = json.load(f)

token = config_data.get("api", {}).get("telegram", {}).get("bot_token")
chat_id = config_data.get("api", {}).get("telegram", {}).get("chat_id")

print(f"Testing Telegram connection with Chat ID: {chat_id}")
url = f"https://api.telegram.org/bot{token}/sendMessage"
payload = {"chat_id": chat_id, "text": "Test from Antigravity"}

try:
    print("Sending request...")
    response = requests.post(url, json=payload, timeout=5)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"🔥 Error: {e}")
