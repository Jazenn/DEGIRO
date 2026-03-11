import toml
from drive_utils import DriveStorage
from managers import ConfigManager

def check_cloud_config():
    with open(".streamlit/secrets.toml", "r", encoding="utf-8") as f:
        secrets = toml.load(f)
        creds = secrets.get("connections", {}).get("gsheets", {})
        
    DRIVE_FOLDER_ID = "16Y7kU4XDSbDjMUfBWU5695FSUWYjq26N"
    drive = DriveStorage(creds, DRIVE_FOLDER_ID)
    
    config = ConfigManager(drive=drive)
    print("Cloud Mappings:")
    for k, v in config.get_mappings().items():
        print(f"'{k}': '{v}'")

if __name__ == '__main__':
    check_cloud_config()
