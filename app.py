import os
import logging
from flask import Flask, request, jsonify, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier
from google_drive_client import get_drive_service, ensure_folder_exists, log_to_sheet
from asana_client import create_project

# Load env vars
load_dotenv()

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

import threading
import time

# Cache for deduplication
PROCESSED_CACHE = {}
CACHE_TTL = 3600  # 1 hour

def is_processed(channel_id):
    """Check if channel_id was processed recently."""
    cleanup_cache()
    return channel_id in PROCESSED_CACHE

def mark_processed(channel_id):
    """Mark channel_id as processed with current timestamp."""
    PROCESSED_CACHE[channel_id] = time.time()

def cleanup_cache():
    """Remove old entries from cache."""
    current_time = time.time()
    # Create list of keys to remove
    to_remove = [k for k, v in PROCESSED_CACHE.items() if current_time - v > CACHE_TTL]
    for k in to_remove:
        del PROCESSED_CACHE[k]

# Config
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
GOOGLE_DRIVE_PARENT_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_PARENT_FOLDER_ID")
ASANA_WORKSPACE_ID = os.environ.get("ASANA_WORKSPACE_ID")
ASANA_TEAM_ID = os.environ.get("ASANA_TEAM_ID")
SPREADSHEET_ID = "1lBvtlKicpP_qXwGcKw_CkBOGnuMVHSlYAFC7xhfR3WA"
SHEET_NAME = "Projects"

if SLACK_SIGNING_SECRET:
    verifier = SignatureVerifier(SLACK_SIGNING_SECRET)
else:
    logging.warning("SLACK_SIGNING_SECRET is not set. Signature verification will fail.")
    verifier = None
    verifier = None

slack_client = None
if SLACK_BOT_TOKEN:
    slack_client = WebClient(token=SLACK_BOT_TOKEN)
else:
    logging.warning("SLACK_BOT_TOKEN is not set. Bot actions (invites) will fail.")

# Cache for user IDs
USER_ID_CACHE = {}

def get_user_id_by_name(name):
    """Finds a user's ID by their real name or display name."""
    if name in USER_ID_CACHE:
        return USER_ID_CACHE[name]
    
    if not slack_client:
        return None

    try:
        # Note: listing all users can be slow for large workspaces. 
        # Ideally we paginate, but for a simple bot/small org this is okay.
        cursor = None
        while True:
            response = slack_client.users_list(cursor=cursor)
            members = response['members']
            
            for member in members:
                if member['deleted']:
                    continue
                real_name = member.get('real_name') or ""
                display_name = member.get('profile', {}).get('display_name') or ""
                if name.lower() == real_name.lower() or name.lower() == display_name.lower():
                    USER_ID_CACHE[name] = member['id']
                    return member['id']
            
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
                
        logging.warning(f"User '{name}' not found.")
        return None
    except SlackApiError as e:
        logging.error(f"Error fetching users list: {e}")
        return None

def invite_user_to_channel(channel_id, user_id):
    """Invites a user to a channel."""
    if not slack_client:
        return

    try:
        slack_client.conversations_invite(channel=channel_id, users=[user_id])
        logging.info(f"Invited user {user_id} to channel {channel_id}")
    except SlackApiError as e:
        if e.response['error'] == 'already_in_channel':
            logging.info(f"User {user_id} is already in channel {channel_id}")
        else:
             logging.error(f"Error inviting user {user_id} to channel {channel_id}: {e}")
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

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
            channel_id = channel_info.get("id")
            channel_name = channel_info.get("name")
            
            if channel_id and channel_name:
                # Deduplication check
                if is_processed(channel_id):
                    logging.info(f"Duplicate event for channel {channel_name} ({channel_id}). Skipping.")
                    return jsonify({"status": "duplicate_skipped"}), 200

                # Mark as processed
                mark_processed(channel_id)
                
                # Process in background thread to prevent Slack timeout
                thread = threading.Thread(target=handle_channel_created, args=(channel_name, channel_id))
                thread.start()

    return jsonify({"status": "ok"}), 200

def handle_channel_created(channel_name, channel_id):
    logging.info(f"Processing new channel: {channel_name}")
    # 0. Invite n8n Bot
    try:
        n8n_user_id = get_user_id_by_name("n8n")
        if n8n_user_id:
            invite_user_to_channel(channel_id, n8n_user_id)
        else:
            logging.warning("Could not find user 'n8n' to invite.")
    except Exception as e:
        logging.error(f"Failed to invite n8n bot: {e}")

    folder_id = None
    drive_url = ""
    # 1. Google Drive
    if GOOGLE_DRIVE_PARENT_FOLDER_ID:
        try:
            drive_service = get_drive_service()
            folder_name = f"SEO Work - {channel_name}"
            logging.info(f"Creating/Checking Google Drive folder: {folder_name}")
            folder_id = ensure_folder_exists(drive_service, GOOGLE_DRIVE_PARENT_FOLDER_ID, folder_name)
            if folder_id:
                drive_url = f"https://drive.google.com/drive/folders/{folder_id}"
        except Exception as e:
            logging.error(f"Failed to process Google Drive for {channel_name}: {e}")
    else:
        logging.error("GOOGLE_DRIVE_PARENT_FOLDER_ID is missing.")

    # 2. Asana
    project_gid = None
    asana_url = ""
    if ASANA_WORKSPACE_ID:
        try:
            project_gid = create_project(channel_name, ASANA_WORKSPACE_ID, ASANA_TEAM_ID)
            if project_gid:
                asana_url = f"https://app.asana.com/0/0/{project_gid}/list"
        except Exception as e:
            logging.error(f"Failed to process Asana for {channel_name}: {e}")
    else:
        logging.error("ASANA_WORKSPACE_ID is missing.")

    # 3. Google Sheet Logging
    if SPREADSHEET_ID and SHEET_NAME:
         log_to_sheet(SPREADSHEET_ID, SHEET_NAME, channel_name, drive_url, channel_id, asana_url)

if __name__ == "__main__":
    app.run(port=3000)
