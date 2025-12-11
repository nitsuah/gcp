# gcp

<!-- Status -->
[![Linting](https://github.com/nitsuah/gcp/actions/workflows/pylint.yml/badge.svg)](https://github.com/nitsuah/gcp/actions)
<!-- CI is TBD [![CI](https://github.com/nitsuah/gcp/actions/workflows/pylint.yml/badge.svg)](https://github.com/nitsuah/gcp/actions) -->

**TL;DR-** - A simple script that uses the Google Drive API to generate reports of files and folders and copy all contents from one folder to another.

## Objectives

- Assessment #1 - Write a script to generate a report that shows the total number of files and folders in the root of the source folder.
- Assessment #2 - Write a script to recursively count the number of child objects (all sub-files & folders) for each top-level folder under the source folder.
- Assessment #3 - Write a script to copy content (nested files/folders) of the source folder to destination folder.

## Setup GCP environment

- [Login to GCP & Create project](https://console.cloud.google.com/getting-started?organizationId=0)
- [Create Google OAuth 2.0 Client IDs](https://console.cloud.google.com/apis/credentials/consent?project=project-id)

## Installation

### Prerequisites
- Python 3.10 or higher
- Google Cloud Platform account with Drive API enabled
- OAuth 2.0 Client ID credentials ([setup guide](https://console.cloud.google.com/apis/credentials))

### Install from source

```bash
# Clone the repository
git clone https://github.com/nitsuah/gcp.git
cd gcp

# Install in development mode
pip install -e ".[dev]"

# Verify installation
drive-report --help
```

### Required API Scopes
- `https://www.googleapis.com/auth/drive`
- `https://www.googleapis.com/auth/drive.metadata.readonly`

## Configuration

Set the following environment variables:

```bash
export GOOGLE_DRIVE_CLIENT_ID_FILE='/path/to/client_id.json'
export GOOGLE_DRIVE_SOURCE_FOLDER_ID='your-source-folder-id'
export GOOGLE_DRIVE_DESTINATION_FOLDER_ID='your-destination-folder-id'
```

Or create a `.env` file (see `.env.example`):

```bash
GOOGLE_DRIVE_CLIENT_ID_FILE=/path/to/credentials.json
GOOGLE_DRIVE_SOURCE_FOLDER_ID=abc123xyz
GOOGLE_DRIVE_DESTINATION_FOLDER_ID=xyz456abc
```

## Usage

### CLI Command

```bash
drive-report
```

### Python Module

```python
from gcp.copy_folder import count_files_and_folders, copy_child_objects

# Count files in a folder
num_files, num_folders = count_files_and_folders('folder_id')

# Copy folder contents
copy_child_objects('source_id', 'destination_id')
```

## Output Schema

### CSV Format
```csv
Folder Name,File Count,Folder Count
Design,15,3
Documentation,28,5
TOTAL,43,8
```

### JSON Format
See `examples/report-sample.json` for complete structure.

## Outputs

- [![Assessment-1](https://badgen.net/badge/assessment-1/VALIDATED/green?icon=github)](https://github.com/nitsuah/gcp/blob/main/outputs/assessment-1.csv)
- [![Assessment-2](https://badgen.net/badge/assessment-2/VALIDATED/green?icon=github)](https://github.com/nitsuah/gcp/blob/main/outputs/assessment-2.csv)
- [![Assessment-3](https://badgen.net/badge/assessment-3/VALIDATED/green?icon=github)](https://github.com/nitsuah/gcp/blob/main/outputs/assessment-3.csv)

## Workflows

- [![pylint](https://github.com/nitsuah/gcp/actions/workflows/pylint.yml/badge.svg)](https://github.com/nitsuah/gcp/actions/workflows/pylint.yml)
- [![Bandit](https://github.com/nitsuah/gcp/actions/workflows/bandit.yml/badge.svg)](https://github.com/nitsuah/gcp/actions/workflows/bandit.yml)
- [![CodeQL](https://github.com/nitsuah/gcp/actions/workflows/codeql.yml/badge.svg)](https://github.com/nitsuah/gcp/actions/workflows/codeql.yml)
- [![Dependency Review](https://github.com/nitsuah/gcp/actions/workflows/dependency-review.yml/badge.svg)](https://github.com/nitsuah/gcp/actions/workflows/dependency-review.yml)
