import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
import googleapiclient.http

# Folder and File IDs
SOURCE_FOLDER_ID = '1VU_UKKzholxH6BL_ISRyGyio_TZJ1Uvm'
DESTINATION_FILE_ID = '1j1n1hg4jkhoYSv2Fh5jGT7PuQxI08bbF' 

def get_service():
    creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    creds_dict = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(creds_dict)
    return build('drive', 'v3', credentials=creds)

def find_latest_export(service):
    """Finds the most recent JSON file in the source folder."""
    query = f"'{SOURCE_FOLDER_ID}' in parents and trashed = false"
    results = service.files().list(
        q=query, 
        fields="files(id, name, createdTime)", 
        orderBy="createdTime desc"
    ).execute()
    files = results.get('files', [])

    for file in files:
        if file['name'].endswith('.json') and file['id'] != DESTINATION_FILE_ID:
            print(f"Found latest export: {file['name']}")
            return file['id']
    return None

def sync_data():
    service = get_service()
    latest_file_id = find_latest_export(service)
    
    if not latest_file_id:
        print("No new files found to sync.")
        return

    # Download the content of the newest file
    content = service.files().get_media(fileId=latest_file_id).execute()
    
    # Update the master health_data.json file directly
    media = googleapiclient.http.MediaByteArrayUpload(content, mimetype='application/json')
    
    service.files().update(
        fileId=DESTINATION_FILE_ID,
        media_body=media
    ).execute()
    
    print(f"Sync complete: Master file (ID: {DESTINATION_FILE_ID}) updated successfully.")

if __name__ == "__main__":
    sync_data()
