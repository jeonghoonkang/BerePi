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
from webdav3.client import Client


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

options = {
    'webdav_hostname': None,
    'webdav_login': None,
    'webdav_password': None
}

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
    options['webdav_hostname'] = config['nextcloud']['webdav_hostname']
    options['webdav_login'] = config['nextcloud']['username']
    options['webdav_password'] = config['nextcloud']['password']

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
    # if not os.path.exists(down_dir):
    #     os.makedirs(down_dir)
    os.makedirs(down_dir, exist_ok=True)


# 파일 다운로드
def download_file(conf, filename): #filename = "/2023/09/01/2023-09-01 00-36-40 3799.jpg" 좌측 / 주의 
    
    filename = filename.lstrip("/")
    url = f"{conf['nextcloud']['url']}/remote.php/dav/files/{conf['nextcloud']['username']}{conf['nextcloud']['remote_folder']}"

    path_file = f"{conf['nextcloud']['remote_folder']}/{filename}" # /Photos/biz_card/2023/***.jpg
    path_file = f"{conf['nextcloud']['remote_folder']}"            # /Photos/biz_card
    
    local_path = f"{conf['local']['download_folder']}/{filename}"  #  down_images/2023/강정훈_명함_KETI.jpg

    remote_path = os.path.join(conf['nextcloud']['remote_folder'], filename)    
    local_path = os.path.join(conf['local']['download_folder'], filename)
    #dir_name = os.path.dirname(local_path_dir.lstrip("/"))
    #dir_name = conf['local']['download_folder'] +'/' + dir_name
    #make dir #subdir 이 깊이가 있을 경우는 확인해야함 (현재는 1 depth 만 확인함)
    #os.makedirs(dir_name, exist_ok=True)

    os.makedirs(os.path.dirname(local_path), exist_ok=True)


    client = Client(options)
    #print (f"{debug_prefix} remote dav path: {path_file}")
    #print (f"{debug_prefix} Downloading from {path_file} to {local_path}")
    #client.download_sync(f"{conf['nextcloud']['remote_folder']}", f"{local_path_dir}")

    print (f"{debug_prefix} Downloading from {remote_path} to {local_path}")
    client.download_sync(remote_path, local_path)




# 주기적 실행 함수
def run_periodically(conf, interval_minutes=60):
    print (f"config: {conf}")
    print (f"config: {conf['local']['download_folder']}")
    create_folders(conf.get('local',{}).get('download_folder',''))
    
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
        exit(" run through crontab") 

        time.sleep(interval_minutes * 60)



if __name__ == "__main__":
    # Tesseract 경로 설정 (필요한 경우)
    # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    
    conf = __init__()

    try:
        run_periodically(conf, interval_minutes=5)  # 60분마다 실행
    except KeyboardInterrupt:
        print("Process stopped by user")