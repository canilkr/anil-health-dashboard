import os
import json
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaByteArrayUpload

# Folder IDs
SOURCE_FOLDER_ID = '1VU_UKKzholxH6BL_ISRyGyio_TZJ1Uvm'
DESTINATION_FILE_ID = '1ax2eh1VwB0eO-Gg0Yh62xxLhzSuoedVl' # This is the ID of the master health_data.json

def get_service():
    creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    creds_dict = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(creds_dict)
    return build('drive', 'v3', credentials=creds)

def find_latest_export(service):
    """Finds the most recent JSON file in the source folder."""
    query = f"'{SOURCE_FOLDER_ID}' in parents and trashed = false"
    # Sort by createdTime descending to get the newest file first
    results = service.files().list(
        q=query, 
        fields="files(id, name, createdTime)", 
        orderBy="createdTime desc"
    ).execute()
    files = results.get('files', [])

    for file in files:
        # Grab the first JSON file that isn't the destination file itself
        if file['name'].endswith('.json') and file['id'] != DESTINATION_FILE_ID:
            print(f"Found latest file: {file['name']} (ID: {file['id']})")
            return file['id']
    
    print("No valid JSON files found in the source folder.")
    return None

def sync_data():
    service = get_service()
    
    latest_file_id = find_latest_export(service)
    if not latest_file_id:
        return

    # 1. Download the content of the newest file
    content = service.files().get_media(fileId=latest_file_id).execute()
    
    # 2. Update the master health_data.json file
    media = MediaByteArrayUpload(content, mimetype='application/json')
    
    service.files().update(
        fileId=DESTINATION_FILE_ID,
        media_body=media
    ).execute()
    
    print(f"Successfully updated master health_data.json with data from {latest_file_id}")

if __name__ == "__main__":
    sync_data()
