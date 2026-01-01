import os
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    """Authenticates and returns the Google Drive service."""
    creds = None
    creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    
    if creds_path and os.path.exists(creds_path):
         creds = service_account.Credentials.from_service_account_file(
            creds_path, scopes=SCOPES)
    else:
        logging.error("GOOGLE_APPLICATION_CREDENTIALS not found or invalid.")
        # If running locally with user credentials or other auth, handling could be added here.
        # But for this task, we assume service account.
        raise Exception("GOOGLE_APPLICATION_CREDENTIALS environment variable not set or file missing.")

    return build('drive', 'v3', credentials=creds)

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
