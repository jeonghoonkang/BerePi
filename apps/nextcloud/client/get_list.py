
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
def get_file_list(conf):
    url = f"{conf['nextcloud']['url']}/remote.php/dav/files/{conf['nextcloud']['username']}{conf['nextcloud']['remote_folder']}"
    print (f"URL: {url}")
    USERNAME = conf['nextcloud']['username']
    PASSWORD = conf['nextcloud']['password']
    
    response = requests.request(
        "PROPFIND",
        url,
        auth=HTTPBasicAuth(USERNAME, PASSWORD),
        headers={"Depth": "2"}
    )
    
    if response.status_code != 207:
        print(f"Error accessing Nextcloud: {response.status_code}")
        return []
    
    from xml.etree import ElementTree
    tree = ElementTree.fromstring(response.content)
    files = []
    
    for response in tree.findall("{DAV:}response"):
        href = response.find("{DAV:}href").text
        if href.endswith("/"):
            continue  # 폴더는 건너뜁니다
        
        # 파일명만 추출
        filename = href.split("/")[-1]
        if filename.lower().endswith(('.jpg', '.jpeg')):
            files.append(filename)
    
    return files

def create_folders(down_dir):
    print (f"Creating folders if not exist: {down_dir}")
    if not os.path.exists(down_dir):
        os.makedirs(down_dir)


# 주기적 실행 함수
def run_periodically(conf, interval_minutes=60):
    print (f"config: {conf}")
    print (f"config: {conf['local']['download_folder']}")
    create_folders(conf.get('local',{}).get('download_folder',{}))
    
    while True:
        print(f"\nChecking for new files at {datetime.now()}")
        
        # 파일 목록 가져오기
        files = get_file_list(conf)
        print(f"Found {len(files)} JPG files in Nextcloud")
        print (f"files: {files}")
        # # 각 파일 처리
        # for filename in files:
        #     local_path = download_file(filename)
        #     if local_path:
        #         ocr_text = process_ocr(local_path)
        #         if ocr_text:
        #             save_to_json(filename, ocr_text)
        
        # 대기
        exit("test  ")
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