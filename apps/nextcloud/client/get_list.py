#-*- coding: utf-8 -*-
#Author: https://github.com/jeonghoonkang

import os
import time
import json
import requests
from PIL import Image
import pytesseract
from datetime import datetime
from requests.auth import HTTPBasicAuth
from urllib.parse import unquote_plus
import urllib.parse


# def __init__(self, config_path="tmp_config.json"):
#     self.config = self.load_config(config_path)

    # def load_config(self, config_path):
    #     """설정 파일 로드"""
    #     try:
    #         with open(config_path, 'r', encoding='utf-8') as f:
    #             config = json.load(f)
            
    #         # 필수 설정 확인
    #         required_keys = [
    #             'nextcloud/url', 'nextcloud/username', 'nextcloud/password',
    #             'local/download_folder', 'local/result_json'
    #         ]
            
    #         for key in required_keys:
    #             section, item = key.split('/')
    #             if item not in config.get(section, {}):
    #                 raise ValueError(f"Missing required config: {key}")
            
    #         return config
        
    #     except FileNotFoundError:
    #         raise FileNotFoundError(f"Config file not found: {config_path}")
    #     except json.JSONDecodeError:
    #         raise ValueError(f"Invalid JSON in config file: {config_path}")
    
debug_prefix = "  "

def load_config(config_path):
    """설정 파일 로드"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 필수 설정 확인
        required_keys = [
            'nextcloud/url', 'nextcloud/username', 'nextcloud/password',
            'local/download_folder', 'local/result_json'
        ]
        
        for key in required_keys:
            section, item = key.split('/')
            if item not in config.get(section, {}):
                raise ValueError(f"Missing required config: {key}")
        
        return config
    
    except FileNotFoundError:
        raise FileNotFoundError(f"Config file not found: {config_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON in config file: {config_path}")


def __init__(config_path="tmp_config.json"):
    config = load_config(config_path)
    return config


#url = f"{self.config['nextcloud']['url']}/remote.php/dav/files/{self.config['nextcloud']['username']}{self.config['nextcloud']['remote_folder']}"


# Nextcloud에서 파일 목록 가져오기
def get_file_list_recursive(conf, current_path="", depth=0):
    
    debug_prefix = "  " * depth
    print(f"{debug_prefix}↳ Scanning: {current_path or 'root'} (depth {depth})")

    url = f"{conf['nextcloud']['url']}/remote.php/dav/files/{conf['nextcloud']['username']}{conf['nextcloud']['remote_folder']}{current_path}"
    #using current path to check sub-dir 

    print(f"{debug_prefix}  URL: {url}")  # Debug URL
    
    USERNAME = conf['nextcloud']['username']
    PASSWORD = conf['nextcloud']['password']
    
    response = requests.request(
        "PROPFIND",
        url,
        auth=HTTPBasicAuth(USERNAME, PASSWORD),
        headers={"Depth": "1"},
        timeout = 10
    )

    #print (f"Response: {response.content}")
    #</d:response><d:response><d:href>/remote.php/dav/files/tinyos/Photos/biz_card/2023/%ec%82%ac%ec%a7%84%2023-09-01%2000-36-40%203799.jpg

    if response.status_code != 207:
        print(f"Error accessing Nextcloud: {response.status_code}")
        return []
    
    from xml.etree import ElementTree
    tree = ElementTree.fromstring(response.content)
    files = []
    
    for response_buff in tree.findall("{DAV:}response"):
        
        uhref = response_buff.find("{DAV:}href").text
        relative_path = uhref.replace(f"/remote.php/dav/files/{conf['nextcloud']['username']}{conf['nextcloud']['remote_folder']}", "").lstrip("/")
        print (f"{debug_prefix}  Found uhref: {uhref}")
        print (f"{debug_prefix}  relative_path: {relative_path}")
       
        href = urllib.parse.unquote_plus(uhref)
        decoded_path = urllib.parse.unquote_plus(relative_path)
        #print (f"decoded_path: {decoded_path}")

        if not relative_path: #current dir skip
            print(f"{debug_prefix}  Skipping current directory")
            continue

        print(f"{debug_prefix} Check href  : {href}")
        if href.endswith("/") and relative_path != current_path.lstrip("/"):
            print(f"{debug_prefix}  relative_path : {relative_path}")
            print(f"{debug_prefix}  current_path : {current_path}")
            files.extend(get_file_list_recursive(conf, f"/{relative_path}", depth+1))
            continue  

        # 파일명만 추출
        filename = href.split("/")[-1]
        if filename.lower().endswith(('.jpg', '.jpeg')):
            files.append(current_path+filename)

    #print (f"files: {files}")

    return files

def create_folders(down_dir):
    print (f"Creating folders if not exist: {down_dir}")
    if not os.path.exists(down_dir):
        os.makedirs(down_dir)

# 파일 다운로드
def download_file(conf, filename): #filename = "/2023/09/01/2023-09-01 00-36-40 3799.jpg"
    
    url = f"{conf['nextcloud']['url']}/remote.php/dav/files/{conf['nextcloud']['username']}{conf['nextcloud']['remote_folder']}"

    #url = f"{NEXTCLOUD_URL}/remote.php/dav/files/{USERNAME}{remote_path}"



    remote_path = f"{url}/{filename}"
    local_path = f"{conf['local']['download_folder']}{filename}"

    local_path_dir = os.path.join(conf['local']['download_folder'], filename)
    print (f"local path dir: {local_path_dir}")
    os.makedirs(os.path.dirname(local_path_dir.lstrip("/")), exist_ok=True)
    
    exit()

    #local_path = local_path.lstrip("/")
    print (f"{debug_prefix} filename: {filename}")
    print (f"{debug_prefix} local_path: {local_path}")

    username = conf['nextcloud']['username']
    password = conf['nextcloud']['password']

    print (f"{debug_prefix} Downloading from {remote_path} to {local_path}")

    #exit(f"exit download")

    response = requests.get(
        url,
        auth=HTTPBasicAuth(username, password)
    )
    
    if response.status_code == 200:
        with open(local_path, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded: {filename}")
        return local_path
    else:
        print(f"Failed to download {filename}: {response.status_code}")
        return None


# 주기적 실행 함수
def run_periodically(conf, interval_minutes=60):
    print (f"config: {conf}")
    print (f"config: {conf['local']['download_folder']}")
    create_folders(conf.get('local',{}).get('download_folder',{}))
    
    while True:
        print(f"\nChecking for new files at {datetime.now()}")
        
        # 파일 목록 가져오기
        files = get_file_list_recursive(conf) # 서브디렉토리 포함 
        print(f"Found {len(files)} JPG files in Nextcloud")
        print (f"files: {files}")
        # # 각 파일 처리
        for filename in files:
            local_path = download_file(conf, filename)
        #     if local_path:
        #         ocr_text = process_ocr(local_path)
        #         if ocr_text:
        #             save_to_json(filename, ocr_text)
        
        # 대기
        exit(" run periodically") 
        print(f"Waiting for {interval_minutes} minutes...")
        time.sleep(interval_minutes * 60)



if __name__ == "__main__":
    # Tesseract 경로 설정 (필요한 경우)
    # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    
    conf = __init__()

    try:
        run_periodically(conf, interval_minutes=5)  # 60분마다 실행
    except KeyboardInterrupt:
        print("Process stopped by user")