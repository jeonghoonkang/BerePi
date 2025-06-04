import cv2     #sudo pip3 install opencv-python
import numpy as np
import os
import sys
import torch    #sudo pip3 install torch
import json
import time
import argparse
import configparser
from datetime import datetime, timedelta
import re
import shutil

import easyocr
import pytesseract  # check out language pack for tesseract 
                    # tesseract --list-langs # dir: /usr/local/share/tessdata
                    # https://cjsal95.tistory.com/25
                    # for m1 mac, https://simmigyeong.tistory.com/3
                      # brew install tesseract
                      # brew install tesseract-lang # for language pack
                      # tesseract --list-langs # check installed language pack

                    
import inspect

NEXTCLOUD_PHOTOS_DIR = None

options = {
    'webdav_hostname': None,
    'webdav_login': None,
    'webdav_password': None
}

def __init__(config_path="nocommit_url.ini"): ### INIT CHECK ### You should check if using config.json 
    config = load_config(config_path)
    options['webdav_hostname'] = config['nextcloud']['webdav_hostname']
    options['webdav_login'] = config['nextcloud']['username']
    options['webdav_password'] = config['nextcloud']['password']

    return config


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



def load_config(config_path):
    """Load default paths from an ini file."""

    defaults = {
        'scan_image_path': './scan_name_card',
        'save_description_path': './save_description',
        'nextcloud_photo_dir' : '/Photos',
    }

    if not os.path.isfile(config_path):
        return defaults

    parser = configparser.ConfigParser()
    with open(config_path, 'r') as cfg:
        content = cfg.read()
    # ocr_name_card.ini does not have a section header. Prepend a default one.
    parser.read_string('[DEFAULT]\n' + content)
    cfg_defaults = parser['DEFAULT']

    defaults['scan_image_path'] = cfg_defaults.get('scan_image_path', defaults['scan_image_path']).strip("\"'")
    defaults['save_description_path'] = cfg_defaults.get('save_description_path', defaults['save_description_path']).strip("\"'")
    defaults['nextcloud_photo_dir'] = cfg_defaults.get('nextcloud_photo_dir', defaults['nextcloud_photo_dir']).strip("\"'")
    
    global NEXTCLOUD_PHOTOS_DIR
    NEXTCLOUD_PHOTOS_DIR = defaults['nextcloud_photo_dir']


    #print (NEXTCLOUD_PHOTOS_DIR)
    #exit()
    
    return defaults


def recursive_search_dir(_nowDir, _filelist): # 재귀적으로 디렉토리 탐색
    
    dir_list = []
    
    f_list = os.listdir(_nowDir) # 현재 디렉토리의 파일 리스트

    for fname in f_list: # 파일 리스트를 하나씩 읽어들임
        if os.path.isdir(_nowDir + '/' + fname): # 디렉토리면 dir_list에 추가
            dir_list.append(_nowDir + '/' + fname)
        elif os.path.isfile(_nowDir + '/' + fname): # 파일이면 _filelist에 추가
            file_extension = os.path.splitext(fname)[-1]
            if file_extension == ".jpg" or file_extension == ".JPG":
                _filelist.append(_nowDir + '/' + fname)
        
    for _dir in dir_list: # dir_list에 있는 디렉토리에 대해 재귀적으로 탐색
            recursive_search_dir(_dir, _filelist)


def printProgressBar(iteration, total, prefix = 'Progress', suffix = 'Complete',\
                      decimals = 1, length = 50, fill = '█'): 
    # 작업의 진행상황을 표시
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print('\r%s |%s| %s%% %s' %(prefix, bar, percent, suffix), end='\r')
    sys.stdout.flush()
    if iteration == total:
        print()

def ctime_to_datetime(ctime): # 생성시간을 datetime으로 변환
    return datetime.fromtimestamp(ctime)

def analysis(file, model):

    img = cv2.imread(file)
    results = model(img)

    json_data = []

    for result in results.xyxy[0]:
        if result[4] > 0.5: # confidence가 0.5 이상인 객체만 저장
            data = { # json에 저장할 데이터
                'name' : model.names[int(result[5])], # 객체 이름
            }
            json_data.append(data)

    return json_data


# 객체 탐색
def save_image(file, model, save_path): 

    img = cv2.imread(file)
    results = model(img)

    for result in results.xyxy[0]:
        if result[4] > 0.5: # confidence가 0.5 이상인 객체만 저장
            # 객체 위치에 사각형 그리기
            img = cv2.rectangle(img, (int(result[0]), int(result[1])), (int(result[2]), int(result[3])), (0, 255, 0), 2)
            # 객체 이름을 사각형 위에 표시
            img = cv2.putText(img, model.names[int(result[5])], (int(result[0]), int(result[1])-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    filename = file.split('/')[-1]    
    save_path = save_path + "/" + filename

    cv2.imwrite(save_path, img)

def merge_json_files(file_list, save_path, conf):

    json_data = []

    print(file_list, save_path)
    
    for file in file_list:
        with open(file, 'r',  encoding='utf-8') as json_file:
            data = json.load(json_file)
        # data가 리스트인 경우와 단일 객체인 경우를 구분하여 처리
        if isinstance(data, list):
            json_data.extend(data)  # 리스트 병합
        else:
            json_data.append(data)  # 단일 객체 추가
    
    print ("  ####  json_data", json_data)

    # Load existing data if the output file already exists
    if os.path.isfile(save_path):
        try:
            with open(save_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                if isinstance(existing, list):
                    json_data.extend(existing)
                else:
                    json_data.append(existing)
        except json.JSONDecodeError:
            pass

    merged = {}
    for item in json_data:
        key = item.get('filepath') or item.get('filename')
        if key is None:
            continue

        # 새로운 키가 없으면 추가
        if key not in merged:
            merged[key] = item
            continue

        # Combine fields without overwriting existing non-empty values
        for k, v in item.items():
           # If the current item has a non-empty value, always use it
            if v:
                merged[key][k] = v
                continue

            # When the new value is empty but an old value exists,
            # keep the old value and propagate it to the current item
            if k in merged[key] and merged[key][k]:
                item[k] = merged[key][k]
            else:
                merged[key][k] = v

    merged_values = list(merged.values())

    with open(save_path, 'w', encoding='utf-8') as json_file:
        json.dump(merged_values, json_file, ensure_ascii=False, indent=2)

    # Save an additional file with a timestamp in the filename
    time_suffix = datetime.now().strftime('%Y%m%d_%H%M%S')
    base, ext = os.path.splitext(save_path)
    timestamped_path = f"{base}_{time_suffix}{ext}"
    with open(timestamped_path, 'w', encoding='utf-8') as json_file:
        json.dump(merged_values, json_file, ensure_ascii=False, indent=2)

    remove_old_timestamped_files(save_path)
    
    # Copy the resulting files to Nextcloud if configured
    copy_to_nextcloud([save_path, timestamped_path], conf)


def remove_old_timestamped_files(save_path, months=3):
    """Delete timestamped JSON files older than the given number of months."""
    base_dir = os.path.dirname(save_path)
    base_name, ext = os.path.splitext(os.path.basename(save_path))
    pattern = re.compile(rf"{re.escape(base_name)}_(\d{{8}}_\d{{6}}){re.escape(ext)}$")
    cutoff = datetime.now() - timedelta(days=30 * months)

    for fname in os.listdir(base_dir):
        match = pattern.match(fname)
        if not match:
            continue
        try:
            file_time = datetime.strptime(match.group(1), "%Y%m%d_%H%M%S")
        except ValueError:
            continue
        if file_time < cutoff:
            try:
                os.remove(os.path.join(base_dir, fname))
            except OSError:
                pass

def copy_to_nextcloud(paths, conf): #(savePath, timestamped_path)  and NEXTCLOUD_PHOTOS_DIR
    """Copy given file paths to a Nextcloud directory if configured."""
    if not conf:
        print("No destination directory provided for Nextcloud.")
        return

    print(f"Copying files to Nextcloud directory: {dest_dir}")
    #os.makedirs(dest_dir, exist_ok=True)

    #options['webdav_hostname']
    #options['webdav_login']
    #options['webdav_password']

    if options['webdav_hostname'] and options['webdav_login'] and options['webdav_password']:
        try:
            from webdav3.client import Client  # type: ignore

            client = Client(options)
            client.verify = True

            for src in paths:
                if not src:
                    continue

                remote_path = os.path.join(dest_dir, os.path.basename(src))
                
                try:
                    client.upload_sync(remote_path=remote_path, local_path=src)
                except Exception as e:  # noqa: BLE001
                    print(f"Failed to upload {src} to {remote_path}: {e}")
            return
        except Exception as e:  # noqa: BLE001
            print(f"WebDAV upload failed: {e}; falling back to local copy")


    exit("### exit tinyos ### on the copy to nextcloud") # for the on the step to run this code

    return dest_dir

def ocr():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-lang', '--language', help='language, ko, ja', default='ko')
    argparser.add_argument('-f', '--file', help='file name', default='./sample.jpg')
    args = argparser.parse_args()

    file_name = args.file
    language = args.language
    print(language)
    print (file_name)

    reader = easyocr.Reader(['en',language]) #language is changing string

    chk_string = ["ko","ja"]
    #for chk in chk_string:
        #print (chk)

    if (not any( chk in language for chk in chk_string)): # if language is not in chk_string:
        print (language)
        print ("language is not in ko, ja")
        sys.exit("language mismatch")
        
    print (file_name, language)
    fpath = file_name

    #fpath='/home/tinyos/devel_opment/data/ocr/sample_receipt.png'
    reader = easyocr.Reader([language,'en']) #language

    #print (sys.argv)
    result = reader.readtext(fpath)

    pprint(result, depth=5, indent=4)


def test_func(file, run_flag=True):

    if run_flag == False:
        print("### NO run test_func ###")
        print ("test_func is not running")
        return None


    print(inspect.getfile(pytesseract))
    
    oem = 3
    psm = 4
    custom_config = ' --oem ' + str(oem) + ' --psm ' + str(psm) 
    #custom_config = ' --oem ' + str(oem) + ' --psm ' + str(psm) + ' -c --preserve_interword_spaces=1 '
    namecard_img = cv2.imread(file)
    gray = cv2.cvtColor(namecard_img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 3)
    txt = pytesseract.image_to_string(gray, lang='kor+eng', config=custom_config)

    #print (txt) 
    return txt

if __name__=='__main__':
    #exit("for the first run test") # for the first step to run this code

    # if (sys.argv is None) or (len(sys.argv) < 3):
    #     print("Usage: (입력 인자를 추가해 주세요) python run_ocr_name_card.py [scan_name_card] [save_description]")
    #     sys.exit(1) 

    parser = argparse.ArgumentParser(description='명함 문자 인식', usage='bash run.sh')
    # parser.add_argument('scan_name_card', type=str, help='명함 스캔 이미지 파일이 있는 디렉토리 경로')
    # parser.add_argument('save_description', type=str, help='결과 내용 저장할 디렉토리 경로')
    parser.add_argument('scan_name_card', nargs='?', help='명함 스캔 이미지 파일이 있는 디렉토리 경로')
    parser.add_argument('save_description', nargs='?', help='결과 내용 저장할 디렉토리 경로')
    parser.add_argument('-c', '--config', default='ocr_name_card.ini', help='초기 설정 파일 경로')
    args = parser.parse_args()

    conf = __init__()


    #dir_path = sys.argv[1]
    config = load_config(args.config)
    dir_path = args.scan_name_card or config['scan_image_path']
    dir_path = os.path.abspath(dir_path)    # 절대경로로 변환
    #save_path = sys.argv[2]
    save_path = args.save_description or config['save_description_path']
    save_path = os.path.abspath(save_path)  # 절대경로로 변환

    file_list = []
    json_data = []
    json_file_list = []
    cnt = 0
    start_time = time.time()
    
    recursive_search_dir(dir_path, file_list)

    print("\n명함 파일 개수 : %d" % len(file_list))

    run_flag = False # test_func를 실행할지 여부

    
    for file in file_list:
        cnt += 1
        printProgressBar(cnt, len(file_list))
        print ("processing", file)
        #print ("### to do: code more")
        buff = test_func(file, run_flag)
        #test
        filename = file.split('/')[-1]         # 파일명
        filepath = save_path + '/' + filename  # 파일경로
        ctime = os.path.getctime(file)         # 생성시간
        json_file_path = os.path.splitext(filepath)[0] + '.json'

        ctime = ctime_to_datetime(ctime).strftime('%Y-%m-%d %H:%M:%S') # 생성시간 datetime으로 변환
        # 원본이미지 파일 경로도 저장
        original_filepath = dir_path + '/' + filename
        data = {
            'filename' : json_file_path.split('/')[-1], # json 파일명
            'filepath' : json_file_path,
            'ctime' : ctime,
            'original_filepath' : original_filepath,
            'ocr' : buff,
            'name' : "",
            'company' : "",
            'email' : "",
            'cellphone' : "",
            'phone' : "",
        }

        with open(json_file_path, 'w',  encoding='utf-8') as json_file:
            json.dump(data, json_file, ensure_ascii=False, indent=2)

        json_file_list.append(json_file_path)

    file_path = save_path + '/file_list.json'
    merge_json_files(json_file_list, file_path)

    exit("### exit tinyos ### on the test check for good here ") # for the on the step to run this code



#   # 객체 탐지 모델 로드
    result_cnt = 0

    with open(file_path, 'r') as json_file:
        json_data = json.load(json_file)
        # 만약에 result가 None이 아니라면, result_cnt를 1 증가
        for data in json_data:
            if data['result'] is not None:
                result_cnt += 1


    print("\n객체 탐지 결과가 있는 이미지 파일 개수 : %d" % result_cnt)
    print("객체 탐지 결과가 없는 이미지 파일 개수 : %d" % (len(file_list) - result_cnt))

    # 객체 이름을 출력하고 개수를 출력(result에 여러 개의 동일 객체 이름은 하나로 취급)
    class_cnt = {}
    for data in json_data:
        if data['result']:
            for result in data['result']:
                # result 내에 값을 통해 객체 이름에 대한 딕셔너리 생성
                obj_name = []
                # 1개 이상의 객체 이름이 있는 경우에 대해 한개만 추가
                if result['name'] not in obj_name:
                    obj_name.append(result['name'])
                # class_cnt에 해당 내용을 추가
            for name in obj_name:
                if name in class_cnt:
                    class_cnt[name] += 1
                else:
                    class_cnt[name] = 1
    
    # 해당 내용을 json 파일로 저장
    # 현재 디렉토리
    now_dir = os.getcwd()
    class_cnt_path = now_dir + '/search_keyword/class_cnt.json'
    print ("\n객체 이름과 개수를 저장할 JSON 파일 경로 : ", class_cnt_path)
    
    with open(class_cnt_path, 'w') as json_file:
        json.dump(class_cnt, json_file, indent=2)
        print(class_cnt)

    print("\n객체 이름과 개수를 저장한 JSON 파일 생성 완료")

    end_time = time.time()

    print("\n걸린 시간 : ", end_time - start_time)
