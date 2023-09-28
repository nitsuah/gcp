# ABOUT

This script uses the Google Drive API to count the number of files and folders in a specified folder, and then copies the top-level folder to a specified destination folder.
The script also logs any errors encountered during the copying process.

## Functions

- count_files_and_folders(folder_id): Counts the number of files and folders in a specified folder.
- copy_child_objects(source_folder_id, destination_folder_id): Copies all child objects (files and folders) of a specified folder to a specified destination folder.
- handle_copy_error(file_or_folder_name, error): Handles errors encountered during the copying process.
- count_child_objects(folder_id): Counts the number of child folders in a specified folder recursively.

## Parameters

- folder_id: The ID of the folder to count or copy.
- source_folder_id: The ID of the source folder to copy.
- destination_folder_id: The ID of the destination folder to copy to.
- file_or_folder_name: The name of the file or folder that encountered an error.
- error: The error encountered during the copying process.

## Implementations

- The script reads the client ID JSON file path from the environment variable 'GOOGLE_DRIVE_CLIENT_ID_FILE'.
- The script checks if the environment variable is set, and raises a ValueError if it is not.
- The script creates a flow to handle the OAuth2 authentication.
- The script authenticates and authorizes the user.
- The script checks if the credentials are valid, and prints a message if they are not.
- The script creates a Google Drive API service object.
- The script specifies the source and destination folder IDs.
- The script defines a function to count files and folders, which uses the Google Drive API to list the files and folders in a specified folder and count them.
- The script defines a function to copy child objects recursively, which uses the Google Drive API to list the files and folders in a specified folder, copy the files to the destination folder, and recursively copy the child folders to the destination folder.
- The script defines a function to handle copy errors, which logs the error to a log file and a CSV file, and retrieves the parent folder URLs if the error is related to copying a file.
- The script defines a function to count child objects recursively, which uses the Google Drive API to list the child folders in a specified folder, count them, and recursively count the child folders in each top-level folder.
- The script gets the count for the specified folder using the count_files_and_folders() function.
- The script writes the results to a CSV file.
- The script copies the top-level source folder to the provided destination folder using the copy_child_objects() function.
