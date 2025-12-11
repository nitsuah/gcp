'''
A script using the Google Drive API to create reports and copy contents between folders.
'''
import os
import csv
import logging
import datetime
import pandas as pd
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError # pylint: disable=ungrouped-imports

# Define API scopes
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]

# Environment variables
CLIENT_ID_ENV_VAR = 'GOOGLE_DRIVE_CLIENT_ID_FILE'
SOURCE_FOLDER_ID_ENV_VAR = 'GOOGLE_DRIVE_SOURCE_FOLDER_ID'
DESTINATION_FOLDER_ID_ENV_VAR = 'GOOGLE_DRIVE_DESTINATION_FOLDER_ID'

# Script Constants
MISSING_ENVAR_TXT = 'Missing environment variable for'
MIME_FOLDER = 'application/vnd.google-apps.folder'

# Directories and filenames
OUTPUTS_DIRECTORY = './outputs/'

# Get the current timestamp
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d%H%M')

# Create a logger for better error tracking
LOG_FILENAME = f'gcp-{TIMESTAMP}.log'
LOG_FILE_PATH = os.path.join(OUTPUTS_DIRECTORY, LOG_FILENAME)
LOG_FILE_FORMAT='%(asctime)s %(levelname)s %(message)s %(filename)s %(funcName)s %(lineno)d'
logging.basicConfig(filename=LOG_FILE_PATH, level=logging.INFO, format=LOG_FILE_FORMAT)

# Read client ID JSON file path from the environment variable
CLIENT_ID_FILE = os.environ.get(CLIENT_ID_ENV_VAR)

# Specify the source folder ID
source_folder_id = os.environ.get(SOURCE_FOLDER_ID_ENV_VAR)

# Specify the destination folder ID
destination_folder_id = os.environ.get(DESTINATION_FOLDER_ID_ENV_VAR)

# Check if the environment variables are set
if not CLIENT_ID_FILE:
    raise ValueError(f"{MISSING_ENVAR_TXT} Google Drive API Client ID JSON: {CLIENT_ID_ENV_VAR}")
if not source_folder_id:
    raise ValueError(f"{MISSING_ENVAR_TXT} Source folder ID: {SOURCE_FOLDER_ID_ENV_VAR}")
if not destination_folder_id:
    raise ValueError(f"{MISSING_ENVAR_TXT} Destination folder ID: {DESTINATION_FOLDER_ID_ENV_VAR}")

# Create a flow to handle the OAuth2 authentication
def authenticate_and_authorize(client_id_file, api_scopes):
    """
    Handles OAuth2 authentication and authorization.

    Args:
        client_id_file (str): The path to the client ID JSON file.
        api_scopes (list): The list of API scopes.

    Returns:
        credentials (google.oauth2.credentials.Credentials): The authorized credentials.
    """
    flow = InstalledAppFlow.from_client_secrets_file(client_id_file, api_scopes)
    auth_credentials = flow.run_local_server()

    if auth_credentials and auth_credentials.valid:
        return auth_credentials
    return None

def create_drive_service(valid_credentials):
    """
    Creates a Google Drive API service object.

    Args:
        valid_credentials (google.oauth2.credentials.Credentials): The authorized credentials.

    Returns:
        service (googleapiclient.discovery.Resource): The Drive API service object.
    """
    return build('drive', 'v3', credentials=valid_credentials)

# Authenticate and authorize the user
authed_credentials = authenticate_and_authorize(CLIENT_ID_FILE, SCOPES)

# Check if credentials are valid
if authed_credentials:
    service = create_drive_service(authed_credentials)
else:
    logging.error("Authorization failed.")
    raise RuntimeError("Failed to authenticate with Google Drive API")

# MAGIC Constants - to improve readability & linting
# Disable pylint for no-member at the function level
# pylint: disable=no-member
source_folder_name = service.files().get(fileId=source_folder_id, fields='name').execute()
destination_folder_name = service.files().get(fileId=destination_folder_id, fields='name').execute()

# Define a function to count files and folders
def count_files_and_folders(folder_id):
    """
    Counts the number of FILES and FOLDERS in a given folder_id.

    Args:
        folder_id (str): The ID of the folder to count files and folders in.

    Returns:
        num_files (int): The total number of files in the folder.
        num_folders (int): The total number of folders in the folder.
    """
    # Count Files
    query = (f"'{folder_id}' in parents and mimeType != '{MIME_FOLDER}' "
             f"and trashed = false")
    results = service.files().list(q=query).execute()
    files = results.get('files', [])
    num_files = len(files)
    # Count Folders
    query = (f"'{folder_id}' in parents and mimeType = '{MIME_FOLDER}' "
             f"and trashed = false")
    results = service.files().list(q=query).execute()
    folders = results.get('files', [])
    num_folders = len(folders)

    return num_files, num_folders

# Define a function to count child objects recursively
def count_child_objects(folder_id):
    """
    Recursively counts the number of files and folders in a given folder and its subfolders.

    Args:
        folder_id (str): The ID of the folder to count files and folders for.

    Returns:
        num_files (int): The total number of files in the folder and its subfolders.
        num_folders (int): The total number of folders in the folder and its subfolders.
    """
    query = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(q=query).execute()
    files_and_folders = results.get('files', [])
    num_files = 0
    num_folders = 0

    for item in files_and_folders:
        if item['mimeType'] == 'application/vnd.google-apps.folder':
            # It's a folder, increment folder count
            child_num_files, child_num_folders = count_child_objects(item['id'])
            num_files += child_num_files
            num_folders += child_num_folders + 1
        else:
            # It's a file, increment file count
            num_files += 1

    return num_files, num_folders

# Define a function to copy child objects recursively
def copy_child_objects(src_folder_id, dest_folder_id, max_retries=1):
    """
    Copies all child objects (files and folders) from source folder to a destination folder.
    Includes a static retry mechanism for file copy failures.

    Args:
        src_folder_id (str): The id for the source folder.
        dest_folder_id (str): The id for the destination folder.
        max_retries=1 (int): The maximum number of times to retry copying a file before giving up.
    """
    # List files in the source folder
    query = f"'{src_folder_id}' in parents"
    results = service.files().list(q=query).execute()
    files = results.get('files', [])

    try:
        # Copy each file to the destination folder
        for file in files:
            file_metadata = {'name': file['name'], 'parents': [dest_folder_id]}
            # Retry loop
            for retry_attempt in range(max_retries):
                try:
                    # Attempt to copy the file
                    service.files().copy(fileId=file['id'], body=file_metadata).execute()
                    # If the copy is successful, break out of the retry loop
                    break
                except HttpError as error_msg:
                    if retry_attempt < max_retries - 1:
                        # Log the error and retry
                        logging.error("Error copying file %s, retrying... (%d/%d)",
                                      file['name'], retry_attempt + 1, max_retries)
                    else:
                        # If all retries fail, log the error and move on to the next file
                        logging.error("Error copying file %s after %d retries: %s",
                                      file['name'], max_retries, error_msg)
                        break

    except HttpError as error_msg:
        # Handle errors related to copying files
        handle_copy_error(file['name'], error_msg)

    # List folders in the source folder
    query = f"'{src_folder_id}' in parents and mimeType = '{MIME_FOLDER}'"
    results = service.files().list(q=query).execute()
    folders = results.get('files', [])

    # Recursively copy child objects to the destination folder while preserving structure
    for folder in folders:
        # Create a new folder in the destination with the same name
        new_folder_metadata = {
            'name': folder['name'],
            'parents': [dest_folder_id],
            'mimeType': 'application/vnd.google-apps.folder'
        }
        new_folder = service.files().create(body=new_folder_metadata, fields='id').execute()
        # Recursively copy the child objects into the new folder
        copy_child_objects(folder['id'], new_folder['id'])

# Define a function to handle copy errors
def handle_copy_error(file_or_folder_name, error):
    """
    Logs the error message and retrieves the parent folder(s) of the file if possible.

    Args:
        file_or_folder_name (str): The name of the file or folder that failed to copy.
        error (Exception): The error that occurred while copying the file or folder.
    """
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
                logging.error('Folder URL: %s', folder_url)
        except HttpError as error_msg:
            logging.error('ERROR-PARENT: %s', error_msg)

    # Write the error to the log file
    logging.error('COPY FAILED: %s: %s', file_or_folder_name, error)

# Define a function to recursively add child records to the CSV
def add_child_folders(folder_id):
    """
    Recursively adds child folders to the CSV file.

    Args:
        folder_id (str): The ID of the folder to add child folders for.
    """
    query = (f"'{folder_id}' in parents and "
         f"mimeType = '{MIME_FOLDER}' and "
         f"trashed = false")
    results = service.files().list(q=query, orderBy='name asc').execute()
    folders = results.get('files', [])
    for folder in folders:
        folder_id = folder['id']
        num_files, num_folders = count_child_objects(folder_id)
        WRITER.writerow([folder['name'], num_files, num_folders])

# Enable pylint for no-member again
# pylint: enable=no-member

logging.info("STARTING ASSESSMENTS...")
# ASSESSEMENT 1 - Write the results to a CSV file
csv_file = './outputs/assessment-1.csv'
with open(csv_file, 'w', newline='', encoding='utf-8') as output_file:
    # Get the name of the source folder
    total_num_files, total_num_folders = count_child_objects(source_folder_id)
    WRITER = csv.writer(output_file)
    WRITER.writerow(['Folder Name', 'Number of Files', 'Number of Folders'])
    WRITER.writerow([source_folder_name['name'], total_num_files, total_num_folders])

# ASSESSEMENT 2 - Write the results to a CSV file
csv_file = './outputs/assessment-2.csv'
with open(csv_file, 'w', newline='', encoding='utf-8') as output_file:
    WRITER = csv.writer(output_file)
    WRITER.writerow(['Folder Name', 'Number of Files', 'Number of Child Folders'])
    # Write the Total at the top of the CSV
    total_num_files, total_num_folders = count_child_objects(source_folder_id)
    WRITER.writerow(['TOTAL', total_num_files, total_num_folders])
    add_child_folders(source_folder_id)

# Copy all child objects (including nested folders and files) to the new top-level folder

logging.info("STARTING COPY TO %s...", destination_folder_name['name'])
copy_child_objects(source_folder_id, destination_folder_id)
logging.info("COPY COMPLETED!")

# ASSESSEMENT 3 - Write the results to a CSV file
csv_file = './outputs/assessment-3.csv'
with open(csv_file, 'w', newline='', encoding='utf-8') as output_file:
    WRITER = csv.writer(output_file)
    WRITER.writerow(['Folder Name', 'Number of Files', 'Number of Child Folders'])

    # Write the Total at the top of the CSV
    total_num_files, total_num_folders = count_child_objects(destination_folder_id)
    WRITER.writerow(['TOTAL', total_num_files, total_num_folders])
    add_child_folders(destination_folder_id)

logging.info("ASSESSMENTS COMPLETED!")

logging.info("STARTING VALIDATION...")
# Compare the two assessments CSV files
def compare_csv_files(file1, file2):
    """
    Compare two CSV files and log whether they are equal or not.

    Args:
        file1 (str): The path to the first CSV file.
        file2 (str): The path to the second CSV file.
    """
    # Read the CSV files into pandas DataFrames
    assessment2 = pd.read_csv(file1)
    assessment3 = pd.read_csv(file2)

    # Check if the DataFrames are equal
    if assessment2.equals(assessment3):
        logging.info("VALIDATION SUCCESSFUL!")
    else:
        logging.error("VALIDATION FAILED - Source & Destination folder counts do not match.")
        print("ERROR: VALIDATION FAILED!")

# Load source and destination file count CSV reports
OUTPUT_2 = './outputs/assessment-2.csv'
OUTPUT_3 = './outputs/assessment-3.csv'

compare_csv_files(OUTPUT_2, OUTPUT_3)

# FINISH SCRIPT
logging.info("COPIED: " + source_folder_name['name'] +
             " to " + destination_folder_name['name'])
print("SCRIPT COMPLETED!")

def main():
    """Main entry point for CLI."""
    print("Google Drive Report & Copy Tool")
    print("Running copy_folder script...")
    # Script already runs when module is imported
    # This is kept for backwards compatibility

if __name__ == "__main__":
    main()
