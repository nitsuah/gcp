import os
import csv
from google.oauth2 import credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]

# Read client ID JSON file path from the environment variable
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

    except HttpError as e:
        handle_copy_error(file['name'], e)

    query = f"'{source_folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
    results = service.files().list(q=query).execute()
    folders = results.get('files', [])
    
    try:
        # Recursively copy child objects to the destination folder
        for folder in folders:
            folder_metadata = {'name': folder['name'], 'parents': [destination_folder_id], 'mimeType': 'application/vnd.google-apps.folder'}
            new_folder = service.files().create(body=folder_metadata, fields='id, name').execute()
            copy_child_objects(folder['id'], new_folder['id'])  # Pass new folder's ID

    except HttpError as e:
        handle_copy_error(folder['name'], e)

# Define a function to handle copy errors
def handle_copy_error(file_or_folder_name, error):
    # If the error is related to copying a file, try to retrieve its parent folder(s)
    if isinstance(error, HttpError) and 'fileId' in error.__dict__:
        file_id = error.__dict__['fileId']
        try:
            # Retrieve the file's metadata to get parent folder(s)
            file_metadata = service.files().get(fileId=file_id, fields='parents').execute()
            parent_folder_ids = file_metadata.get('parents', [])
            
            # Construct URLs to the parent folders based on their IDs
            for folder_id in parent_folder_ids:
                folder_url = f'https://drive.google.com/drive/folders/{folder_id}'
                print(f'Parent Folder URL: {folder_url}')
        except Exception as e:
            print(f"ERROR-PARENT: {e}")

        # Write the error to a log file
        with open('./outputs/error.log', 'a') as log_file:
            log_file.write(f"ERROR: {file_or_folder_name}: {error}\n")
            
        # Write the error to a CSV file
        with open('./outputs/errors.csv', 'a', newline='') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow([file_or_folder_name, error])

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

    return num_folders

# Get the count for the specified folder
num_files, num_folders = count_files_and_folders(source_folder_id)

# Write the results to a CSV file
csv_file = './outputs/assessment-1.csv'
with open(csv_file, 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['Number of Files', num_files])
    writer.writerow(['Number of Folders', num_folders])

# Copy the top-level source folder to the provided destination folder
source_folder_metadata = service.files().get(fileId=source_folder_id, fields='name').execute()
destination_folder_metadata = {'name': source_folder_metadata['name'], 'parents': [destination_folder_id], 'mimeType': 'application/vnd.google-apps.folder'}
new_folder = service.files().create(body=destination_folder_metadata, fields='id, name').execute()

# Copy child objects (including nested folders) to the new top-level folder
copy_child_objects(source_folder_id, new_folder['id'])

# Write the child object count to a CSV file
csv_file = './outputs/assessment-2.csv'
with open(csv_file, 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['Folder Name', 'Number of Files', 'Number of Folders', 'Number of Child Folders'])

    # Add the top-level folder to the CSV
    writer.writerow([source_folder_metadata['name'], num_files, num_folders, count_child_objects(new_folder['id'])])

    # Recursively add child folders to the CSV
    def add_child_folders(folder_id):
        query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
        results = service.files().list(q=query).execute()
        folders = results.get('files', [])
        for folder in folders:
            folder_id = folder['id']
            writer.writerow([folder['name'], count_files_and_folders(folder_id)[0], count_files_and_folders(folder_id)[1], count_child_objects(folder_id)])
            add_child_folders(folder_id)

    add_child_folders(new_folder['id'])

# Count child objects in destination folder
count_child_objects(destination_folder_id)

# Write the child object count in destination to a CSV file
csv_file = './outputs/assessment-3.csv'
with open(csv_file, 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['Destination Folder Name', 'Number of Files', 'Number of Folders', 'Number of Child Folders'])

    # Add the top-level folder to the CSV
    writer.writerow([destination_folder_metadata['name'], num_files, num_folders, count_child_objects(new_folder['id'])])

    # Recursively add child folders to the CSV
    def add_child_folders(folder_id):
        query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
        results = service.files().list(q=query).execute()
        folders = results.get('files', [])
        for folder in folders:
            folder_id = folder['id']
            writer.writerow([folder['name'], count_files_and_folders(folder_id)[0], count_files_and_folders(folder_id)[1], count_child_objects(folder_id)])
            add_child_folders(folder_id)

    add_child_folders(new_folder['id'])

print("COPY COMPLETED!")