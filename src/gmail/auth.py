"""
Gmail API authentication module
"""
import os
import pickle
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',  # Read and modify but not delete
    'https://www.googleapis.com/auth/gmail.labels',  # Manage labels
]

def get_client_config():
    """Get OAuth client configuration from environment variables"""
    return {
        "installed": {
            "client_id": os.getenv("GMAIL_CLIENT_ID"),
            "project_id": os.getenv("GMAIL_PROJECT_ID"),
            "auth_uri": os.getenv("GMAIL_AUTH_URI"),
            "token_uri": os.getenv("GMAIL_TOKEN_URI"),
            "auth_provider_x509_cert_url": os.getenv("GMAIL_AUTH_PROVIDER_CERT_URL"),
            "client_secret": os.getenv("GMAIL_CLIENT_SECRET"),
            "redirect_uris": ["http://localhost"]
        }
    }

def get_gmail_service():
    """Get an authorized Gmail API service instance."""
    creds = None
    token_file = os.getenv('GMAIL_TOKEN_FILE', '.secrets/token.json')
    
    # Create token directory if it doesn't exist
    token_dir = os.path.dirname(token_file)
    if token_dir and not os.path.exists(token_dir):
        os.makedirs(token_dir)

    # Load existing credentials if they exist
    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_config(
                get_client_config(), 
                SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)

    # Build and return the Gmail service
    return build('gmail', 'v1', credentials=creds)

def get_user_email(service) -> Optional[str]:
    """Get the email address of the authenticated user"""
    try:
        profile = service.users().getProfile(userId='me').execute()
        return profile.get('emailAddress')
    except Exception as e:
        print(f"Error getting user email: {e}")
        return None