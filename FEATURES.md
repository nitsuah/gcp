# GCP Google Drive API Script Features

## Core Capabilities

### 🔐 Authentication & Authorization

- **OAuth2 Authentication**: Secure authentication flow using Google OAuth 2.0 with local server callback
- **Credential Management**: Handles credential validation and authorization token management
- **Client ID Configuration**: Environment variable-based client ID JSON file configuration
- **API Scopes**: Drive full access and metadata read-only scopes

### 📊 Reporting & Analysis

- **Assessment 1 - Root Count**: Generates CSV report showing total files and folders in source folder root
- **Assessment 2 - Recursive Count**: Creates detailed CSV report with recursive child object counts for all top-level folders
- **Assessment 3 - Copy Validation**: Produces CSV report of destination folder contents after copy operation
- **CSV Export**: Automated CSV file generation with structured data format

### 📁 Folder Operations

- **Recursive Copying**: Copies all files and folders from source to destination while preserving directory structure
- **Folder Enumeration**: Counts files and folders at any depth level
- **Child Object Tracking**: Recursively counts and tracks all child files and sub-folders
- **Folder Structure Preservation**: Maintains original folder hierarchy during copy operations

### 🛡️ Error Handling & Reliability

- **Retry Mechanism**: Configurable retry logic for file copy failures (default: 1 retry)
- **Comprehensive Logging**: Detailed logging to timestamped log files in outputs directory
- **Error Recovery**: Graceful error handling with parent folder URL retrieval for failed operations
- **Copy Validation**: Automatic validation comparing source and destination counts after copy

### ✅ Validation & Quality

- **Pandas-Based Validation**: Uses pandas DataFrames to compare CSV reports
- **Automated Verification**: Compares Assessment 2 and Assessment 3 reports to ensure copy accuracy
- **Success Confirmation**: Logs validation results and alerts on mismatches
- **Trashed File Filtering**: Excludes trashed items from all counting and copying operations

## Configuration

### 🔧 Environment Variables

- **GOOGLE_DRIVE_CLIENT_ID_FILE**: Path to OAuth2 client ID JSON file
- **GOOGLE_DRIVE_SOURCE_FOLDER_ID**: Google Drive folder ID to copy from
- **GOOGLE_DRIVE_DESTINATION_FOLDER_ID**: Google Drive folder ID to copy to

## Output Artifacts

### 📄 Generated Files

- **assessment-1.csv**: Root folder file and folder counts
- **assessment-2.csv**: Detailed recursive counts for all child folders
- **assessment-3.csv**: Destination folder validation report
- **gcp-[timestamp].log**: Timestamped log file with operation details and errors
