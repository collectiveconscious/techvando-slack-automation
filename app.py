import os
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from slack_sdk.signature import SignatureVerifier
from google_drive_client import get_drive_service, ensure_folder_exists
from asana_client import create_project

# Load env vars
load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Config
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
GOOGLE_DRIVE_PARENT_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_PARENT_FOLDER_ID")
ASANA_WORKSPACE_ID = os.environ.get("ASANA_WORKSPACE_ID")

if SLACK_SIGNING_SECRET:
    verifier = SignatureVerifier(SLACK_SIGNING_SECRET)
else:
    logging.warning("SLACK_SIGNING_SECRET is not set. Signature verification will fail.")
    verifier = None

@app.route("/slack/events", methods=["POST"])
def slack_events():
    if not verifier:
        return jsonify({"status": "server_configuration_error"}), 500

    if not verifier.is_valid_request(request.get_data(), request.headers):
        return jsonify({"status": "invalid_request"}), 403

    data = request.json
    
    # Slack URL verification challenge
    if data.get("type") == "url_verification":
        return jsonify({"challenge": data.get("challenge")})

    # Event handling
    if "event" in data:
        event = data["event"]
        event_type = event.get("type")

        if event_type == "channel_created":
            # The 'channel' object in 'channel_created' event:
            # "channel": { "id": "C024BE91L", "name": "fun", "created": 1360782804, "creator": "U024BE7LH" }
            channel_info = event.get("channel", {})
            channel_name = channel_info.get("name")
            
            if channel_name:
                handle_channel_created(channel_name)

    return jsonify({"status": "ok"}), 200

def handle_channel_created(channel_name):
    logging.info(f"Processing new channel: {channel_name}")
    
    # 1. Google Drive
    if GOOGLE_DRIVE_PARENT_FOLDER_ID:
        try:
            drive_service = get_drive_service()
            ensure_folder_exists(drive_service, GOOGLE_DRIVE_PARENT_FOLDER_ID, channel_name)
        except Exception as e:
            logging.error(f"Failed to process Google Drive for {channel_name}: {e}")
    else:
        logging.error("GOOGLE_DRIVE_PARENT_FOLDER_ID is missing.")

    # 2. Asana
    if ASANA_WORKSPACE_ID:
        try:
            create_project(channel_name, ASANA_WORKSPACE_ID)
        except Exception as e:
            logging.error(f"Failed to process Asana for {channel_name}: {e}")
    else:
        logging.error("ASANA_WORKSPACE_ID is missing.")

if __name__ == "__main__":
    app.run(port=3000)
