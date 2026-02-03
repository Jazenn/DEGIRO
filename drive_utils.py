import io
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

class DriveStorage:
    def __init__(self, secrets, folder_id):
        """
        secrets: The st.secrets object containing service_account info.
        folder_id: The ID of the Google Drive folder to use.
        """
        # Mapping Streamlit secrets to the format Google expects
        creds_dict = {
            "type": secrets["type"],
            "project_id": secrets["project_id"],
            "private_key_id": secrets["private_key_id"],
            "private_key": secrets["private_key"],
            "client_email": secrets["client_email"],
            "client_id": secrets["client_id"],
            "auth_uri": secrets["auth_uri"],
            "token_uri": secrets["token_uri"],
            "auth_provider_x509_cert_url": secrets["auth_provider_x509_cert_url"],
            "client_x509_cert_url": secrets["client_x509_cert_url"],
            "universe_domain": secrets.get("universe_domain", "googleapis.com")
        }
        
        self.scopes = ["https://www.googleapis.com/auth/drive"]
        self.creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=self.scopes
        )
        self.service = build("drive", "v3", credentials=self.creds)
        self.folder_id = folder_id
        self.filename = "transactions_master.xlsx"

    def _find_file(self):
        """Find the Excel file in the target folder."""
        query = f"name = '{self.filename}' and '{self.folder_id}' in parents and trashed = false"
        results = self.service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
        files = results.get("files", [])
        return files[0]["id"] if files else None

    def load_data(self) -> pd.DataFrame:
        """Download the Excel file and return as a DataFrame."""
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
        # Using openpyxl as engine
        return pd.read_excel(fh, engine="openpyxl")

    def save_data(self, df: pd.DataFrame):
        """Upload or update the Excel file from a DataFrame."""
        fh = io.BytesIO()
        with pd.ExcelWriter(fh, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        
        fh.seek(0)
        media = MediaIoBaseUpload(fh, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", resumable=True)
        
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
