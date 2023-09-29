# ABOUT

This script uses the Google Drive API to count the number of files and folders in a specified folder, and then copies the top-level folder to a specified destination folder. The script also logs any errors encountered during the copying process.

## Functions

- `count_files_and_folders(folder_id)`: Counts the number of files and folders in a specified folder.
- `count_child_objects(folder_id)`: Counts the number of child folders in a specified folder recursively.
- `copy_child_objects(source_folder_id, destination_folder_id)`: Copies all child objects (files and folders) of a specified source folder to a destination folder.
- `handle_copy_error(file_or_folder_name, error)`: Handles errors encountered during the copying process.

## Parameters

- `folder_id`: The ID of the folder to count or copy.
- `source_folder_id`: The ID of the source folder to copy.
- `destination_folder_id`: The ID of the destination folder to copy to.
- `file_or_folder_name`: The name of the file or folder that encountered an error.
- `error`: The error encountered during the copying process.

## Implementations

- The script reads the client ID JSON file path from the environment variable `GOOGLE_DRIVE_CLIENT_ID_FILE`.
- The script checks if the environment variables for source and destination folders are set and raises a ValueError if they are not.
- The script creates a flow to handle OAuth2 authentication with the Google Drive API.
- It authenticates and authorizes the user using the obtained credentials.
- The script checks if the credentials are valid and prints a message if they are not.
- It creates a Google Drive API service object for interacting with Google Drive.
- The script defines a function to count files and folders, utilizing the Google Drive API to list and count files and folders in a specified folder.
- A function to copy child objects recursively is defined, allowing the script to list files and folders in a specified folder, copy the files to the destination folder, and recursively copy child folders to the destination folder.
- A function to handle copy errors is included, which logs errors to a log file and retrieves parent folder URLs if the error is related to copying a file.
- The script defines a function to count child objects recursively, counting child folders in a specified folder and recursively counting child folders in each top-level folder.
- It retrieves the count for the specified folder using the `count_files_and_folders()` function.
- The script writes the results to a CSV file.
- The top-level source folder is copied to the provided destination folder using the `copy_child_objects()` function.
