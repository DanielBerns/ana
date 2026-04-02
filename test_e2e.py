import httpx
import argparse

def trigger_chat_flow(message: str):
    print(f"🚀 Firing chat payload to the Ana Interface Gateway...")
    print(f"💬 Message: '{message}'")

    try:
        response = httpx.post(
            "http://localhost:8000/webhook/chat",
            json={"user_id": "architect_01", "message": message},
            timeout=5.0
        )
        print(f"✅ Gateway Acknowledged: {response.status_code}")
        print(f"📦 Payload: {response.json()}")
        print("\n👀 Now, check your terminal running docker-compose to watch the event cascade through the core!")
    except Exception as e:
        print(f"❌ Failed to reach gateway: {e}")

if __name__ == "__main__":
    # Setup CLI argument parsing
    parser = argparse.ArgumentParser(description="Send a test message to Ana's Interface Gateway.")
    parser.add_argument(
        "message",
        type=str,
        nargs="?", # Makes the argument optional
        default="Initiate system diagnostic.",
        help="The raw text message you want Ana's neurosymbolic layer to perceive."
    )

    args = parser.parse_args()
    trigger_chat_flow(args.message)
