# ABOUT

This script utilizes the Google Drive API to enumerate the number of files and folders within a specified folder. It then proceeds to copy the top-level folder contents to a destination folder, with a comprehensive logging mechanism for encountered errors during the copying process. Finally it performs a validation step to ensure that the number of files and folders in the destination folder matches the number of files and folders in the source folder.

## Functions

- `count_files_and_folders(folder_id)`: Counts the number of files and folders in a specified folder.
- `count_child_objects(folder_id)`: Counts the number of child folders in a specified folder recursively.
- `copy_child_objects(source_folder_id, destination_folder_id, max_retries=1)`: Copies all child objects (files and folders) of a specified source folder to a destination folder, with an optional retry mechanism for file copy failures.
- `handle_copy_error(file_or_folder_name, error)`: Handles errors encountered during the copying process.

## Parameters

- `folder_id`: The ID of the folder to count or copy.
- `source_folder_id`: The ID of the source folder to copy.
- `destination_folder_id`: The ID of the destination folder to copy to.
- `file_or_folder_name`: The name of the file or folder that encountered an error.
- `error`: The error encountered during the copying process.

## Implementations

- The script reads the client ID JSON file path from the environment variable `GOOGLE_DRIVE_CLIENT_ID_FILE`.
- It checks if the environment variables for source and destination folders are set and raises a ValueError if they are not.
- The script creates a flow to handle OAuth2 authentication with the Google Drive API.
- It authenticates and authorizes the user using the obtained credentials.
- The script checks if the credentials are valid and prints a message if they are not.
- It creates a Google Drive API service object for interacting with Google Drive.
- The script defines a function to count files and folders, utilizing the Google Drive API to list and count files and folders in a specified folder.
- A function to copy child objects recursively is defined, allowing the script to list files and folders in a specified folder, copy the files to the destination folder, and recursively copy child folders to the destination folder. It includes a retry mechanism for file copy failures.
- A function to handle copy errors is included, which logs errors to a log file and retrieves parent folder URLs if the error is related to copying a file.
- The script defines a function to count child objects recursively, counting child folders in a specified folder and recursively counting child folders in each top-level folder.
- It retrieves the count for the specified folder using the `count_files_and_folders()` function.
- The script writes the results to a CSV file.
- The source folder contents (all files & folders) are copied to the provided destination folder using the `copy_child_objects()` function, including a retry mechanism for file copy failures.

- The script specifically performs three assessments:
  1. **ASSESSMENT 1**: Writes the results of counting all files and folders in a source folder to a CSV file.
  2. **ASSESSMENT 2**: Writes the results of counting all files and folders for the first root children folder, as well as child folders, recursively to a CSV file.
  3. **ASSESSMENT 3**: Copies the source folder contents to the provided destination folder and writes the count of files and child folders found at the destination to a CSV file.

- The script includes a validation step:
  - It compares the CSV reports generated in ASSESSMENT 2 and ASSESSMENT 3 using the `compare_csv_files()` function. The validation is deemed successful if the reports match, and an error message is displayed if they do not.

- The script concludes with a success message indicating that the folder contents has been copied from the source to the destination.
