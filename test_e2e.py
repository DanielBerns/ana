import httpx

def trigger_chat_flow():
    print("🚀 Firing chat payload to the Ana Interface Gateway...")
    try:
        response = httpx.post(
            "http://localhost:8000/webhook/chat",
            json={"user_id": "architect_01", "message": "Initiate system diagnostic."},
            timeout=5.0
        )
        print(f"✅ Gateway Acknowledged: {response.status_code}")
        print(f"📦 Payload: {response.json()}")
        print("\n👀 Now, check your terminal running docker-compose to watch the event cascade through the core!")
    except Exception as e:
        print(f"❌ Failed to reach gateway: {e}")

if __name__ == "__main__":
    trigger_chat_flow()
