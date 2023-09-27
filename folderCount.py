import os
import csv
from google.oauth2 import credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

# Define the API scopes you need
SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly', 'https://www.googleapis.com/auth/drive']

# Read client ID JSON file path from environment variable
client_id_file = os.environ.get('GOOGLE_DRIVE_CLIENT_ID_FILE')

# Check if the environment variable is set
if not client_id_file:
    raise ValueError("Missing environment variable for Google Drive API Client ID JSON file.")

# Create a flow to handle the OAuth2 authentication
flow = InstalledAppFlow.from_client_secrets_file(client_id_file, SCOPES)

# Authenticate and authorize the user
credentials = flow.run_local_server()

# Check if credentials are valid
if credentials and credentials.valid:
    pass
else:
    print("Authentication failed.")

# Create a Google Drive API service object
service = build('drive', 'v3', credentials=credentials)

# Specify the source folder ID
source_folder_id = os.environ.get('GOOGLE_DRIVE_SOURCE_FOLDER_ID')

# Specify the destination folder ID
destination_folder_id = os.environ.get('GOOGLE_DRIVE_DESTINATION_FOLDER_ID')

# Define a function to count files and folders
def count_files_and_folders(folder_id):
    query = f"'{folder_id}' in parents"
    results = service.files().list(q=query).execute()
    files = results.get('files', [])
    num_files = len(files)

    query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
    results = service.files().list(q=query).execute()
    folders = results.get('files', [])
    num_folders = len(folders)

    return num_files, num_folders

# Define a function to count child objects recursively
def count_child_objects(folder_id):
    query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
    results = service.files().list(q=query).execute()
    folders = results.get('files', [])
    num_folders = len(folders)

    # Recursively count child objects for each top-level folder
    for folder in folders:
        folder_id = folder['id']
        child_files, child_folders = count_files_and_folders(folder_id)
        num_child_folders = count_child_objects(folder_id)
        num_folders += num_child_folders
        writer.writerow([folder['name'], child_files, child_folders, num_child_folders])

        # Copy the folder to the destination folder
        file_metadata = {'name': folder['name'], 'parents': [destination_folder_id], 'mimeType': 'application/vnd.google-apps.folder'}
        new_folder = service.files().create(body=file_metadata, fields='id').execute()

        # Recursively copy child objects to the new folder
        copy_child_objects(folder_id, new_folder['id'])

    return num_folders

# Define a function to copy child objects recursively
def copy_child_objects(source_folder_id, destination_folder_id):
    query = f"'{source_folder_id}' in parents"
    results = service.files().list(q=query).execute()
    files = results.get('files', [])

    try:
        # Copy each file to the destination folder
        for file in files:
            file_metadata = {'name': file['name'], 'parents': [destination_folder_id]}
            service.files().copy(fileId=file['id'], body=file_metadata).execute()

    except Exception as e:
        print(f"An error occurred while copying files: {str(e)}")

    query = f"'{source_folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
    results = service.files().list(q=query).execute()
    folders = results.get('files', [])
    
    try:
        # Recursively copy child objects to the destination folder
        for folder in folders:
            folder_metadata = {'name': folder['name'], 'parents': [destination_folder_id], 'mimeType': 'application/vnd.google-apps.folder'}
            new_folder = service.files().create(body=folder_metadata, fields='id').execute()
            copy_child_objects(folder['id'], new_folder['id'])

    except Exception as e:
        print(f"An error occurred while copying folders: {str(e)}")


# Get the count for the specified folder
num_files, num_folders = count_files_and_folders(source_folder_id)

# Write the results to a CSV file
csv_file = './outputs/assessment-1.csv'
with open(csv_file, 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['Number of Files', num_files])
    writer.writerow(['Number of Folders', num_folders])

# Write the child object count to a CSV file
csv_file = './outputs/assessment-2.csv'
with open(csv_file, 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['Folder Name', 'Number of Files', 'Number of Folders', 'Number of Child Folders'])
    num_child_folders = count_child_objects(source_folder_id)
    writer.writerow(['Total Nested Folders', '', '', num_child_folders])
    writer.writerow(['Total Folders', '', '', num_folders + num_child_folders])
