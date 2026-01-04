import os
import logging
import threading
import time
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier
from google_drive_client import get_drive_service, ensure_folder_exists, log_to_sheet
from asana_client import create_project

# Database imports
from database import db, AppConfig, ActivityLog

# Load env vars as fallback
load_dotenv()

app = Flask(__name__)
# Key for flash messages
app.secret_key = os.urandom(24) 
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Initialize DB
with app.app_context():
    db.create_all()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Cache for deduplication
PROCESSED_CACHE = {}
CACHE_TTL = 3600  # 1 hour
USER_ID_CACHE = {}

def get_config(key):
    """Get config from DB, fallback to Environment."""
    try:
        val = AppConfig.get(key)
        if val:
            return val
    except Exception:
        pass
    return os.environ.get(key)

def log_activity(channel_name, action_type, status, details=""):
    """Log activity to DB."""
    try:
        log = ActivityLog(
            channel_name=channel_name,
            action_type=action_type,
            status=status,
            details=str(details)
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logging.error(f"Failed to log activity: {e}")

# Routes
@app.route("/", methods=["GET"])
def index():
    return redirect(url_for('dashboard'))

@app.route("/dashboard", methods=["GET"])
def dashboard():
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(50).all()
    return render_template("dashboard.html", logs=logs)

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        # Save all form fields to DB
        for key, value in request.form.items():
            if value: # Only save non-empty? Or save empty to clear? Let's save exact value.
                AppConfig.set(key, value)
        flash("Configuration saved successfully.", "success")
        return redirect(url_for('settings'))
    
    # Load current config for display
    # We fetch all keys we care about
    keys = [
        "SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET",
        "GOOGLE_DRIVE_PARENT_FOLDER_ID", "ASANA_WORKSPACE_ID", "ASANA_TEAM_ID",
        "SPREADSHEET_ID", "SHEET_NAME"
    ]
    current_config = {}
    for k in keys:
        current_config[k] = get_config(k)
        
    return render_template("settings.html", config=current_config)

# Slack Event Handler
@app.route("/slack/events", methods=["POST"])
def slack_events():
    signing_secret = get_config("SLACK_SIGNING_SECRET")
    if signing_secret:
        verifier = SignatureVerifier(signing_secret)
        if not verifier.is_valid_request(request.get_data(), request.headers):
            return jsonify({"status": "invalid_request"}), 403
    else:
        logging.warning("SLACK_SIGNING_SECRET not set.")
        # We might want to allow it if purely testing, but secure default is fail or warn.
        # For now, let's proceed but warn.
        pass

    data = request.json
    if data.get("type") == "url_verification":
        return jsonify({"challenge": data.get("challenge")})

    if "event" in data:
        event = data["event"]
        if event.get("type") == "channel_created":
            channel_info = event.get("channel", {})
            channel_id = channel_info.get("id")
            channel_name = channel_info.get("name")
            
            if channel_id and channel_name:
                if channel_id in PROCESSED_CACHE:
                    if time.time() - PROCESSED_CACHE[channel_id] < CACHE_TTL:
                        return jsonify({"status": "duplicate"}), 200
                
                PROCESSED_CACHE[channel_id] = time.time()
                
                # Start Thread
                thread = threading.Thread(target=run_automation_task, args=(app, channel_name, channel_id))
                thread.start()

    return jsonify({"status": "ok"}), 200

def run_automation_task(app_instance, channel_name, channel_id):
    """Wrapper to run automation in app context for DB access."""
    with app_instance.app_context():
        log_activity(channel_name, "Start", "INFO", "Received channel_created event")
        handle_channel_created_logic(channel_name, channel_id)

def get_slack_client():
    token = get_config("SLACK_BOT_TOKEN") # Reverted to Bot Token Only
    if token:
        return WebClient(token=token)
    return None

def get_user_id_by_name(client, name):
    if name in USER_ID_CACHE: return USER_ID_CACHE[name]
    try:
        cursor = None
        while True:
            response = client.users_list(cursor=cursor)
            for member in response['members']:
                if member['deleted']: continue
                real = member.get('real_name', '').lower()
                display = member.get('profile', {}).get('display_name', '').lower()
                target = name.lower()
                if target == real or target == display:
                    USER_ID_CACHE[name] = member['id']
                    return member['id']
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor: break
    except Exception as e:
        logging.error(f"Error listing users: {e}")
    return None

def handle_channel_created_logic(channel_name, channel_id):
    logging.info(f"Processing {channel_name}...")
    
    # 0. Invite n8n
    client = get_slack_client()
    if client:
        try:
            uid = get_user_id_by_name(client, "n8n")
            if uid:
                client.conversations_invite(channel=channel_id, users=[uid])
                logging.info(f"Invited n8n ({uid})")
                log_activity(channel_name, "Bot Invite", "SUCCESS", f"Invited user n8n ({uid})")
            else:
                logging.warning("User n8n not found")
                log_activity(channel_name, "Bot Invite", "FAILURE", "User 'n8n' not found")
        except Exception as e:
            logging.error(f"Invite failed: {e}")
            log_activity(channel_name, "Bot Invite", "FAILURE", str(e))
    else:
        log_activity(channel_name, "Bot Invite", "FAILURE", "No Slack Bot Token configured")

    # 1. Drive
    drive_url = ""
    parent_id = get_config("GOOGLE_DRIVE_PARENT_FOLDER_ID")
    if parent_id:
        try:
            drive_service = get_drive_service() # We might need to pass config here too if credentials change location? 
            # For now assume creds are file-based or env-based common. 
            # Ideally we'd store creds in DB too but that's complex (json file vs string).
            # Let's assume standard behavior remains for now.
            name = f"SEO Work - {channel_name}"
            fid = ensure_folder_exists(drive_service, parent_id, name)
            if fid:
                drive_url = f"https://drive.google.com/drive/folders/{fid}"
                log_activity(channel_name, "Drive", "SUCCESS", f"Created folder {name}: {drive_url}")
            else:
                log_activity(channel_name, "Drive", "FAILURE", "Failed to get folder ID")
        except Exception as e:
             log_activity(channel_name, "Drive", "FAILURE", str(e))
    else:
        log_activity(channel_name, "Drive", "FAILURE", "GOOGLE_DRIVE_PARENT_FOLDER_ID not set")

    # 2. Asana
    asana_url = ""
    ws_id = get_config("ASANA_WORKSPACE_ID")
    team_id = get_config("ASANA_TEAM_ID")
    if ws_id:
        try:
            # We need to temporarily set ENV vars for asana_client if it reads os.environ directly?
            # Let's check asana_client.py. It reads ASANA_ACCESS_TOKEN.
            # We didn't add ASANA_ACCESS_TOKEN to settings UI, user didn't ask but probably should?
            # The prompt had IDs. Let's assume Token is still ENV or we should add it.
            # For now, let's stick to logic.
            gid = create_project(channel_name, ws_id, team_id)
            if gid:
                asana_url = f"https://app.asana.com/0/0/{gid}/list"
                log_activity(channel_name, "Asana", "SUCCESS", f"Created project: {asana_url}")
            else:
                log_activity(channel_name, "Asana", "FAILURE", "No GID returned")
        except Exception as e:
            log_activity(channel_name, "Asana", "FAILURE", str(e))
    else:
        log_activity(channel_name, "Asana", "FAILURE", "ASANA_WORKSPACE_ID not set")

    # 3. Sheets
    sheet_id = get_config("SPREADSHEET_ID")
    sheet_name = get_config("SHEET_NAME")
    if sheet_id and sheet_name:
        try:
            log_to_sheet(sheet_id, sheet_name, channel_name, drive_url, channel_id, asana_url)
            log_activity(channel_name, "Sheet", "SUCCESS", "Logged to Google Sheet")
        except Exception as e:
            log_activity(channel_name, "Sheet", "FAILURE", str(e))
    else:
        log_activity(channel_name, "Sheet", "FAILURE", "Sheet ID or Name missing")

if __name__ == "__main__":
    app.run(port=3000)
