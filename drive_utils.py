import io
import os
import pandas as pd
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
import json

class DriveStorage:
    def __init__(self, folder_id):
        def get_secret(key):
            # Try streamlit secrets first
            if key in st.secrets:
                return st.secrets[key]
            # Fallback to environment variables
            if key in os.environ:
                return os.environ[key]
            raise KeyError(f"Secret '{key}' not found in st.secrets or os.environ")

        creds_dict = {
            "type": "service_account",
            "project_id": get_secret("GCP_PROJECT_ID"),
            "private_key_id": get_secret("GCP_PRIVATE_KEY_ID"),
            "private_key": get_secret("GCP_PRIVATE_KEY").replace("\\n", "\n"),
            "client_email": get_secret("GCP_CLIENT_EMAIL"),
            "client_id": get_secret("GCP_CLIENT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/v1/certs",
            "client_x509_cert_url": get_secret("GCP_CLIENT_X509_CERT_URL"),
            "universe_domain": "googleapis.com"
        }
        
        self.scopes = ["https://www.googleapis.com/auth/drive"]
        self.creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=self.scopes
        )
        self.service = build("drive", "v3", credentials=self.creds)
        self.folder_id = folder_id
        self.filename = "transactions_master.csv"

    def _find_file(self, filename=None):
        """Find the file in the target folder."""
        target_name = filename if filename else self.filename
        query = f"name = '{target_name}' and '{self.folder_id}' in parents and trashed = false"
        results = self.service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
        files = results.get("files", [])
        return files[0]["id"] if files else None

    def load_data(self) -> pd.DataFrame:
        """Download the CSV file and return as a DataFrame."""
        file_id = self._find_file()
        if not file_id:
            return pd.DataFrame()

        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        fh.seek(0)
        # Read as CSV
        try:
            return pd.read_csv(fh)
        except Exception:
            # If file is empty, return empty DF
            return pd.DataFrame()

    def save_data(self, df: pd.DataFrame):
        """Upload or update the CSV file from a DataFrame."""
        fh = io.BytesIO()
        df.to_csv(fh, index=False, encoding="utf-8")
        
        fh.seek(0)
        # Direct upload (resumable=False) works better for quota-less service accounts
        media = MediaIoBaseUpload(fh, mimetype="text/csv", resumable=False)
        
        file_id = self._find_file()
        if file_id:
            # Update existing
            self.service.files().update(fileId=file_id, media_body=media).execute()
        else:
            # Create new
            file_metadata = {
                "name": self.filename,
                "parents": [self.folder_id]
            }
            self.service.files().create(body=file_metadata, media_body=media, fields="id").execute()

    def load_json(self, filename: str) -> dict | None:
        """Download a JSON file and return as dict."""
        file_id = self._find_file(filename)
        if not file_id:
            return None

        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        fh.seek(0)
        try:
            return json.load(fh)
        except Exception:
            return None

    def save_json(self, filename: str, data: dict):
        """Upload or update a JSON file from a dict."""
        fh = io.BytesIO()
        # Ensure UTF-8 text is written to the BytesIO buffer
        fh.write(json.dumps(data, indent=2).encode('utf-8'))
        
        fh.seek(0)
        media = MediaIoBaseUpload(fh, mimetype="application/json", resumable=False)
        
        file_id = self._find_file(filename)
        if file_id:
            # Update existing
            self.service.files().update(fileId=file_id, media_body=media).execute()
        else:
            # Create new
            file_metadata = {
                "name": filename,
                "parents": [self.folder_id]
            }
            self.service.files().create(body=file_metadata, media_body=media, fields="id").execute()
