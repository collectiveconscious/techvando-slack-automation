import os
import logging
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive']
SHEETS_SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def _get_credentials(scopes):
    """Authenticates and returns the Google credentials."""
    creds = None
    
    # 1. Try User Credentials (token.json) - Preferred for Ownership
    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', scopes)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
        except Exception as e:
            # Only warn if we really expected this to work (e.g. for Drive).
            # For Sheets, we might expect failure if token.json lacks scope.
            logging.warning(f"Failed to load/refresh token.json with scopes {scopes}: {e}")
            creds = None

    # 2. Fallback to Service Account
    if not creds:
        creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if creds_path and os.path.exists(creds_path):
             logging.info(f"Using Service Account credentials for scopes {scopes}.")
             creds = service_account.Credentials.from_service_account_file(
                creds_path, scopes=scopes)
        else:
            logging.error("No valid credentials found (token.json or valid GOOGLE_APPLICATION_CREDENTIALS).")
            # We can return None or raise, but let's let build() fail or raise here.
            raise Exception("No valid credentials found.")
    else:
        logging.info(f"Using User Credential (HassanKhan Online) for scopes {scopes}.")

    return creds

def get_drive_service():
    """Authenticates and returns the Google Drive service."""
    creds = _get_credentials(DRIVE_SCOPES)
    return build('drive', 'v3', credentials=creds)

def get_sheets_service():
    """Authenticates and returns the Google Sheets service."""
    creds = _get_credentials(SHEETS_SCOPES)
    return build('sheets', 'v4', credentials=creds)

def ensure_folder_exists(service, parent_id, folder_name):
    """
    Checks if a folder with the given name exists under parent_id.
    If yes, returns its ID.
    If no, creates it and returns the new ID.
    """
    try:
        # Query for existing folder
        # Note: 'name' query is case-insensitive usually, but strict search is good.
        query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and '{parent_id}' in parents and trashed=false"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = results.get('files', [])

        if files:
            logging.info(f"Folder '{folder_name}' found with ID: {files[0]['id']}")
            return files[0]['id']
        else:
            # Create the folder
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            file = service.files().create(body=file_metadata, fields='id').execute()
            logging.info(f"Folder '{folder_name}' created with ID: {file.get('id')}")
            return file.get('id')

    except HttpError as error:
        logging.error(f"An error occurred with Google Drive API: {error}")
        return None

def log_to_sheet(spreadsheet_id, sheet_name, channel_name, drive_url, channel_id, asana_url):
    """
    Logs the details to the specified Google Sheet.
    """
    try:
        service = get_sheets_service()
        
        creds = None
        if hasattr(service, '_http') and hasattr(service._http, 'credentials'):
             creds = service._http.credentials
        
        email_used = "Unknown"
        if hasattr(creds, 'service_account_email'):
             email_used = creds.service_account_email
             logging.info(f"Using Service Account: {email_used}")
             logging.info(f"IMPORTANT: Please share the Google Sheet with: {email_used}")
        elif creds:
             logging.info("Using User Credentials (should be HassanKhan Online).")
        else:
             logging.info("Could not determine credentials type.")

        # 2. Prepare the row data
        # Columns: A=Channel Name, G=Drive URL, H=Channel ID, I=Asana URL
        # A, B, C, D, E, F, G, H, I
        # 0, 1, 2, 3, 4, 5, 6, 7, 8
        values = [[
            channel_name, # A
            "", "", "", "", "", # B-F
            drive_url,    # G
            channel_id,   # H
            asana_url     # I
        ]]
        
        body = {
            'values': values
        }
        
        # 3. Append to the sheet
        # We use 'USER_ENTERED' to allow parsing if needed, or 'RAW'
        range_name = f"'{sheet_name}'!A:I"
        logging.info(f"Appending to range: {range_name}")
        
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id, range=range_name,
            valueInputOption='USER_ENTERED', body=body).execute()
            
        logging.info(f"{result.get('updates').get('updatedCells')} cells appended to sheet.")

    except HttpError as error:
        logging.error(f"An error occurred with Google Sheets API: {error}")
        if 'email_used' in locals() and email_used != "Unknown":
             logging.error(f"Please ensure {email_used} has Editor access to the Sheet.")
        else:
             logging.error("Please ensure the Service Account has Editor access to the Sheet.")
    except Exception as e:
        logging.error(f"Unexpected error logging to sheet: {e}")
