#Author: https://github.com/jeonghoonkang

import os
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path


# JSON 설정 파일 읽기
#with open('config.json', 'r') as f:
#    config = json.load(f)
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

SOURCE_DIR = os.getenv("SOURCE_DIR")
WEBDAV_URL = os.getenv("WEBDAV_URL")
AUTH = (os.getenv("WEBDAV_USER"), os.getenv("WEBDAV_PW"))

# to do , fix it

def upload_recent_files():
    now = datetime.now()
    threshold = now - timedelta(minutes=15)

    for filename in os.listdir(SOURCE_DIR):
        file_path = os.path.join(SOURCE_DIR, filename)
        if os.path.isfile(file_path):
            if datetime.fromtimestamp(os.path.getmtime(file_path)) > threshold:
                with open(file_path, 'rb') as f:
                    response = requests.put(f"{WEBDAV_URL}/{filename}", data=f, auth=AUTH)
                    print(f"{filename}: {response.status_code}")

if __name__ == "__main__":
    upload_recent_files()
