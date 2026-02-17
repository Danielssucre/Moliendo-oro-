import requests
import json
from pathlib import Path

def debug_updates():
    config_file = Path("config/api_keys.json")
    with open(config_file, 'r') as f:
        keys = json.load(f)
    
    token = keys.get("telegram", {}).get("bot_token")
    chat_id = keys.get("telegram", {}).get("chat_id")
    
    print(f"Token: {token[:10]}...{token[-5:]}")
    print(f"Chat ID Esperado: {chat_id}")
    
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        response = requests.get(url, params={"limit": 5, "offset": -1})
        data = response.json()
        print(f"Respuesta API: {json.dumps(data, indent=2)}")
        
        updates = data.get("result", [])
        if not updates:
            print("No se encontraron actualizaciones pendientes.")
        else:
            for u in updates:
                msg = u.get("message", {})
                cid = str(msg.get("chat", {}).get("id"))
                text = msg.get("text", "")
                print(f"Update ID: {u['update_id']} | Chat ID: {cid} | Text: {text}")
                if cid == str(chat_id):
                    print("✅ MATCH con el Chat ID configurado.")
                else:
                    print("❌ NO MATCH con el Chat ID configurado.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_updates()
