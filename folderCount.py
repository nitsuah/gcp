import os
import csv
import logging
import datetime
from google.oauth2 import credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError

# Define API scopes
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]

# Environment variables
CLIENT_ID_ENV_VAR = 'GOOGLE_DRIVE_CLIENT_ID_FILE'
SOURCE_FOLDER_ID_ENV_VAR = 'GOOGLE_DRIVE_SOURCE_FOLDER_ID'
DESTINATION_FOLDER_ID_ENV_VAR = 'GOOGLE_DRIVE_DESTINATION_FOLDER_ID'

# Directories and filenames
OUTPUTS_DIRECTORY = './outputs/'

# Get the current timestamp
timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M')

# Set up the log file name with the timestamp
ERROR_LOG_FILENAME = f'error-{timestamp}.log'

# Create a logger for better error tracking
logging.basicConfig(filename=os.path.join(OUTPUTS_DIRECTORY, ERROR_LOG_FILENAME), level=logging.ERROR)

# Read client ID JSON file path from the environment variable
client_id_file = os.environ.get(CLIENT_ID_ENV_VAR)

# Specify the source folder ID
source_folder_id = os.environ.get(SOURCE_FOLDER_ID_ENV_VAR)

# Specify the destination folder ID
destination_folder_id = os.environ.get(DESTINATION_FOLDER_ID_ENV_VAR)

# Check if the environment variables are set
if not client_id_file:
    raise ValueError(f"Missing environment variable for Google Drive API Client ID JSON file: {CLIENT_ID_ENV_VAR}")
if not source_folder_id:
    raise ValueError(f"Missing environment variable for source folder ID: {SOURCE_FOLDER_ID_ENV_VAR}")
if not destination_folder_id:
    raise ValueError(f"Missing environment variable for destination folder ID: {DESTINATION_FOLDER_ID_ENV_VAR}")

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

# Define a function to count files and folders
def count_files_and_folders(folder_id):
    query = f"'{folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder'"
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

    # Recursively copy child objects to the destination folder while preserving structure
    for folder in folders:
        # Create a new folder in the destination with the same name
        new_folder_metadata = {'name': folder['name'], 'parents': [destination_folder_id], 'mimeType': 'application/vnd.google-apps.folder'}
        new_folder = service.files().create(body=new_folder_metadata, fields='id').execute()
        # Recursively copy the child objects into the new folder
        copy_child_objects(folder['id'], new_folder['id'])

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
                logging.error(f'Parent Folder URL: {folder_url}')
        except Exception as e:
            logging.error(f"ERROR-PARENT: {e}")

    # Write the error to the log file
    logging.error(f"ERROR: {file_or_folder_name}: {error}")

# Define a function to count child objects recursively
def count_child_objects(folder_id):
    query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
    results = service.files().list(q=query).execute()
    folders = results.get('files', [])
    num_folders = len(folders)
    num_files = 0  # Initialize the count of files for this folder

    # Recursively count child objects for each top-level folder
    for folder in folders:
        folder_id = folder['id']
        child_files, num_child_folders = count_child_objects(folder_id)
        num_files += child_files
        num_folders += num_child_folders

    return num_files, num_folders

# ASSESSEMENT 1 - Write the results to a CSV file
csv_file = './outputs/assessment-1.csv'
with open(csv_file, 'w', newline='') as file:
    # Get the name of the source folder
    source_folder_name = service.files().get(fileId=source_folder_id, fields='name').execute()
    # Get the count for the specified folder
    num_files, num_folders = count_files_and_folders(source_folder_id)
    writer = csv.writer(file)
    writer.writerow(['Folder Name','Number of Files', 'Number of Folders'])
    writer.writerow([source_folder_name['name'], num_files , num_folders])


# Copy the top-level source folder to the provided destination folder
source_folder_metadata = service.files().get(fileId=source_folder_id, fields='name').execute()
destination_folder_metadata = {'name': source_folder_metadata['name'], 'parents': [destination_folder_id], 'mimeType': 'application/vnd.google-apps.folder'}
new_folder = service.files().create(body=destination_folder_metadata, fields='id, name').execute()

print("STARTING ASSESSMENTS...")

# Write the child object count to a CSV file
csv_file = './outputs/assessment-2.csv'
with open(csv_file, 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['Folder Name', 'Number of Files', 'Number of Folders', 'Number of Child Folders'])
    
    # Add the top-level folder to the CSV
    writer.writerow([source_folder_metadata['name'], num_files, num_folders, count_child_objects(source_folder_id)[1]])

    # Recursively add child folders to the CSV
    def add_child_folders(folder_id):
        query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
        results = service.files().list(q=query).execute()
        folders = results.get('files', [])
        for folder in folders:
            folder_id = folder['id']
            writer.writerow([folder['name'], count_files_and_folders(folder_id)[0], count_files_and_folders(folder_id)[1], count_child_objects(folder_id)[1]])
            add_child_folders(folder_id)

    add_child_folders(source_folder_id)


print("STARTING COPY...")
# Copy child objects (including nested folders) to the new top-level folder // FIXME: COPY OF SOURCE in destination
copy_child_objects(source_folder_id, destination_folder_id)
print("COPY COMPLETED!")

# Write the child object count in destination to a CSV file
csv_file = './outputs/assessment-3.csv'
with open(csv_file, 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['Destination Folder Name', 'Number of Files', 'Number of Folders', 'Number of Child Folders'])

    # Add the top-level folder to the CSV
    writer.writerow([destination_folder_metadata['name'], num_files, num_folders, count_child_objects(destination_folder_id)[1]])

    # Recursively add child folders to the CSV
    def add_child_folders(folder_id):
        query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
        results = service.files().list(q=query).execute()
        folders = results.get('files', [])
        for folder in folders:
            folder_id = folder['id']
            writer.writerow([folder['name'], count_files_and_folders(folder_id)[0], count_files_and_folders(folder_id)[1], count_child_objects(folder_id)[1]])
            add_child_folders(folder_id)

    add_child_folders(destination_folder_id)

print("ASSESSMENTS COMPLETED!")