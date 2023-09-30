import os
import csv
import logging
import datetime
import pandas as pd
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
    query = f"'{folder_id}' in parents"
    results = service.files().list(q=query).execute()
    files_and_folders = results.get('files', [])
    num_files = 0
    num_folders = 0

    for item in files_and_folders:
        if item['mimeType'] == 'application/vnd.google-apps.folder':
            # It's a folder, increment folder count
            num_folders += 1
            # Recursively count child objects for each folder
            num_child_files, num_child_folders = count_child_objects(item['id'])
            num_files += num_child_files
            num_folders += num_child_folders
        else:
            # It's a file, increment file count
            num_files += 1

    return num_files, num_folders

print("STARTING ASSESSMENTS...")
# ASSESSEMENT 1 - Write the results to a CSV file
csv_file = './outputs/assessment-1.csv'
with open(csv_file, 'w', newline='') as file:
    # Get the name of the source folder
    source_folder_name = service.files().get(fileId=source_folder_id, fields='name').execute()
    num_files, num_folders = count_child_objects(source_folder_id)
    writer = csv.writer(file)
    writer.writerow(['Folder Name', 'Number of Files', 'Number of Folders'])
    writer.writerow([source_folder_name['name'], num_files, num_folders])

# ASSESSEMENT 2 - Write the results to a CSV file
csv_file = './outputs/assessment-2.csv'
with open(csv_file, 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['Folder Name', 'Number of Files', 'Number of Child Folders'])
    
    # Write the Total at the top of the CSV
    source_folder_name = service.files().get(fileId=source_folder_id, fields='name').execute()
    num_files, num_folders = count_child_objects(source_folder_id)
    writer.writerow([source_folder_name['name'], num_files, num_folders])

    # Recursively add child folders to the CSV
    def add_child_folders(folder_id):
        query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = service.files().list(q=query, orderBy='name asc').execute()
        folders = results.get('files', [])
        for folder in folders:
            folder_id = folder['id']
            num_files, num_folders = count_child_objects(folder_id)
            writer.writerow([folder['name'], num_files, num_folders])

    add_child_folders(source_folder_id)

# Copy child objects (including nested folders) to the new top-level folder
print("STARTING COPY...")
copy_child_objects(source_folder_id, destination_folder_id)
print("COPY COMPLETED!")

# ASSESSEMENT 3 - Write the results to a CSV file
csv_file = './outputs/assessment-3.csv'
with open(csv_file, 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['Folder Name', 'Number of Files', 'Number of Child Folders'])

    # Write the Total at the top of the CSV
    num_files, num_folders = count_child_objects(destination_folder_id)
    writer.writerow([source_folder_name['name'], num_files, num_folders])

    # Recursively add child folders to the CSV
    def add_child_folders(folder_id):
        query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
        results = service.files().list(q=query, orderBy='name asc').execute()
        folders = results.get('files', [])
        for folder in folders:
            folder_id = folder['id']
            num_files, num_folders = count_child_objects(folder_id)
            writer.writerow([folder['name'], num_files, num_folders])

    add_child_folders(destination_folder_id)

print("ASSESSMENTS COMPLETED!")

print("STARTING VALIDATION...")
# Compare outputs CSV files
def compare_csv_files(file1, file2):
    # Read the CSV files into pandas DataFrames
    af1 = pd.read_csv(file1)
    af2 = pd.read_csv(file2)

    # Check if the DataFrames are equal
    if af1.equals(af2):
        print("VALIDATION SUCCESSFUL!")
    else:
        print("ERROR: Source & Destination folder counts do not match.")
        print("VALIDATION FAILED!")

# Load source and destination file count CSV reports 
output2 = './outputs/assessment-2.csv'
output3 = './outputs/assessment-3.csv'

compare_csv_files(output2, output3)


print("SUCCESS:" + source_folder_id['name'] + " copied to " + destination_folder_id['name'])