import os
from google.oauth2 import credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

# Define the API scopes you need
SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']

# Read client ID JSON file path from environment variable
client_id_file = os.environ.get('GOOGLE_DRIVE_CLIENT_ID_FILE')

# Check if the environment variable is set
if not client_id_file:
    raise ValueError("Missing environment variable for Google Drive API Client ID JSON file.")

# Create a flow to handle the OAuth2 authentication
flow = InstalledAppFlow.from_client_secrets_file(client_id_file, SCOPES)

# Authenticate and authorize the user
credentials = flow.run_local_server()

# Check if credentials contain access token
if credentials and credentials.valid:
    print("Authentication successful.")
else:
    print("Authentication failed.")