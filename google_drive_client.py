import os
import logging
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

def _get_credentials():
    """Authenticates and returns the Google credentials."""
    creds = None
    
    # 1. Try User Credentials (token.json) - Preferred for Ownership
    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
        except Exception as e:
            logging.warning(f"Failed to load/refresh token.json: {e}")
            creds = None

    # 2. Fallback to Service Account
    if not creds:
        creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if creds_path and os.path.exists(creds_path):
             logging.info("Using Service Account credentials.")
             creds = service_account.Credentials.from_service_account_file(
                creds_path, scopes=SCOPES)
        else:
            logging.error("No valid credentials found (token.json or valid GOOGLE_APPLICATION_CREDENTIALS).")
            # We can return None or raise, but let's let build() fail or raise here.
            raise Exception("No valid credentials found.")
    else:
        logging.info("Using User Credential (HassanKhan Online).")

    return creds

def get_drive_service():
    """Authenticates and returns the Google Drive service."""
    creds = _get_credentials()
    return build('drive', 'v3', credentials=creds)

def get_sheets_service():
    """Authenticates and returns the Google Sheets service."""
    creds = _get_credentials()
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

def log_to_sheet(spreadsheet_id, sheet_gid, channel_name, drive_url, channel_id, asana_url):
    """
    Logs the details to the specified Google Sheet.
    """
    try:
        service = get_sheets_service()
        
        # 1. Find the Sheet Name from GID
        sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = sheet_metadata.get('sheets', [])
        sheet_name = None
        for sheet in sheets:
            if str(sheet['properties']['sheetId']) == str(sheet_gid):
                sheet_name = sheet['properties']['title']
                break
        
        if not sheet_name:
            logging.error(f"Could not find sheet with GID {sheet_gid} in spreadsheet {spreadsheet_id}")
            return

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
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id, range=range_name,
            valueInputOption='USER_ENTERED', body=body).execute()
            
        logging.info(f"{result.get('updates').get('updatedCells')} cells appended to sheet.")

    except HttpError as error:
        logging.error(f"An error occurred with Google Sheets API: {error}")
    except Exception as e:
        logging.error(f"Unexpected error logging to sheet: {e}")
