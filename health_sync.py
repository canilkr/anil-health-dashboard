import os
import json
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import io

# --- CONFIGURATION ---
# The folder where Health Auto Export saves daily files
SOURCE_FOLDER_ID = '1VU_UKKzholxH6BL_ISRyGyio_TZJ1Uvm' 
# Your root HealthData folder where the Glide app looks for data
DESTINATION_FOLDER_ID = '1ax2eh1VwB0eO-Gg0Yh62xxLhzSuoedVl'
# The static filename Glide expects
GLIDE_FILE_NAME = 'health_data.json'

def get_drive_service():
    # Uses the service account credentials from your GitHub Secrets / Environment
    creds_json = os.getenv('GOOGLE_SERVICES_JSON')
    info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def find_latest_export(service):
    """Finds the most recent health_data-YYYY-MM-DD.json file."""
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    query = f"'{SOURCE_FOLDER_ID}' in parents and name contains 'health_data-' and trashed = false"
    
    results = service.files().list(q=query, fields="files(id, name, createdTime)", orderBy="name desc").execute()
    items = results.get('files', [])
    
    if not items:
        print("No export files found in the source folder.")
        return None
    
    # Returns the top file (latest date due to 'name desc' sorting)
    print(f"Found latest file: {items[0]['name']}")
    return items[0]

def sync_data():
    service = get_drive_service()
    
    # 1. Get the fresh data
    latest_file = find_latest_export(service)
    if not latest_file:
        return

    # 2. Download the fresh data
    request = service.files().get_media(fileId=latest_file['id'])
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    
    # 3. Find the 'stale' file in the destination to overwrite it
    query_dest = f"'{DESTINATION_FOLDER_ID}' in parents and name = '{GLIDE_FILE_NAME}'"
    dest_results = service.files().list(q=query_dest, fields="files(id)").execute()
    dest_items = dest_results.get('files', [])

    # Prepare file for upload
    fh.seek(0)
    media = MediaFileUpload(latest_file['name'], mimetype='application/json', resumable=True)

    if dest_items:
        # Update existing stale file
        file_id = dest_items[0]['id']
        service.files().update(fileId=file_id, media_body=MediaFileUpload(
            io.BytesIO(fh.getvalue()), mimetype='application/json')).execute()
        print(f"Successfully updated {GLIDE_FILE_NAME} with fresh data.")
    else:
        # Create it if it doesn't exist
        file_metadata = {'name': GLIDE_FILE_NAME, 'parents': [DESTINATION_FOLDER_ID]}
        service.files().create(body=file_metadata, media_body=MediaFileUpload(
            io.BytesIO(fh.getvalue()), mimetype='application/json')).execute()
        print(f"Created new {GLIDE_FILE_NAME} in destination folder.")

if __name__ == "__main__":
    sync_data()
