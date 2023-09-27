# gcp

## Objectives

- Assessment #1 - Write a script to generate a report that shows the total number of files and folders in the root of the source folder.
- Assessment #2 - Write a script to recursively count the number of child objects for each top-level folder under the source folder and the total number of nested folders.
- Assessment #3 - Write a script to copy content (nested files/folders) of the source folder to destination folder.

## Setup GCP environment

- [Login to GCP & Create project](https://console.cloud.google.com/getting-started?organizationId=0)
- [Create Google OAuth 2.0 Client IDs](https://console.cloud.google.com/apis/credentials/consent?project=project-id)

## Setup local environment

- [Create Repo](https://github.com/nitsuah/gcp)
- Local dev setup (see below)

```bash
sudo apt-get update
sudo apt-get install python3
sudo apt-get install python3-pip
sudo pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
export GOOGLE_DRIVE_FOLDER_ID='your-folder-id'
export GOOGLE_DRIVE_CLIENT_ID_FILE='/your/path/to/client_id.json'
```

## Outputs

- [![Assessment-1](https://badgen.net/badge/assessment-1/DONE/green?icon=github)](https://github.com/nitsuah/gcp/blob/main/outputs/assessment-1.csv)
- [![Assessment-2](https://badgen.net/badge/assessment-2/DONE/green?icon=github)](https://github.com/nitsuah/gcp/blob/main/outputs/assessment-2.csv)
- [![Assessment-3](https://badgen.net/badge/assessment-2/IN-PROGRESS/blue?icon=github)](https://github.com/nitsuah/gcp/blob/main/outputs/assessment-3.csv)