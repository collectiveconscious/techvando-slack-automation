import requests
import time
import hmac
import hashlib
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
TARGET_URL = "http://localhost:3000/slack/events"
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "test_secret")

def generate_signature(timestamp, body):
    sig_basestring = f"v0:{timestamp}:{body}".encode('utf-8')
    my_signature = 'v0=' + hmac.new(
        SLACK_SIGNING_SECRET.encode('utf-8'),
        sig_basestring,
        hashlib.sha256
    ).hexdigest()
    return my_signature

def test_channel_created():
    timestamp = str(int(time.time()))
    data = {
        "token": "z26uF87kUO7s",
        "team_id": "T061EG9R6",
        "api_app_id": "A0FF0",
        "event": {
            "type": "channel_created",
            "channel": {
                "id": "C024BE91L",
                "name": "project-alpha-test", 
                "created": 1360782804,
                "creator": "U024BE7LH"
            },
            "event_ts": "1678888888.888888"
        },
        "type": "event_callback",
        "event_id": "Ev0PV1",
        "event_time": 1360782804
    }
    body = json.dumps(data)
    
    signature = generate_signature(timestamp, body)
    
    headers = {
        "Content-Type": "application/json",
        "X-Slack-Request-Timestamp": timestamp,
        "X-Slack-Signature": signature
    }
    
    print(f"Sending request to {TARGET_URL}...")
    try:
        response = requests.post(TARGET_URL, data=body, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    print("Ensure app.py is running on port 3000 (and configured with the same signing secret if checking verification).")
    test_channel_created()
