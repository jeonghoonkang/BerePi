import cv2     #sudo pip3 install opencv-python
import numpy as np
import os
import sys
from datetime import datetime
import torch    #sudo pip3 install torch
import json
import time
import argparse
import easyocr

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

def merge_json_files(file_list, save_path):
    json_data = []
    for file in file_list:
        with open(file, 'r') as json_file:
            data = json.load(json_file)
            json_data.append(data)
    
    with open(save_path, 'w') as json_file:
        json.dump(json_data, json_file, indent=2)


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


if __name__=='__main__':
    #exit("for the first run test") # for the first step to run this code

    if (sys.argv is None) or (len(sys.argv) < 3):
        print("Usage: (입력 인자를 추가해 주세요) python run_ocr_name_card.py [scan_name_card] [save_description]")
        sys.exit(1) 

    parser = argparse.ArgumentParser(description='명함 문자 인식', usage='bash run.sh')
    parser.add_argument('scan_name_card', type=str, help='명함 스캔 이미지 파일이 있는 디렉토리 경로')
    parser.add_argument('save_description', type=str, help='결과 내용 저장할 디렉토리 경로')
    args = parser.parse_args()

    dir_path = sys.argv[1]
    dir_path = os.path.abspath(dir_path)    # 절대경로로 변환
    save_path = sys.argv[2]
    save_path = os.path.abspath(save_path)  # 절대경로로 변환

    file_list = []
    json_data = []
    cnt = 0

    start_time = time.time()

    exit("### tinyos ### on the test check for good here ") # for the on the step to run this code
    
    recursive_search_dir(dir_path, file_list)

    print("\n명함 파일 개수 : %d" % len(file_list))

    
    for file in file_list:
        cnt += 1
        printProgressBar(cnt, len(file_list))

        #save_image(file, model, save_path)

    print('\n파일 객체 탐지 및 객체 탐지 내용을 포함한 JSON 파일 생성 중...')

    dir_list = []
    file_list = []
    json_file_list = []
    cnt = 0

    recursive_search_dir(save_path, file_list)

    for file in file_list:
        cnt += 1
        printProgressBar(cnt, len(file_list))

        filename = file.split('/')[-1]         # 파일명
        filepath = save_path + '/' + filename  # 파일경로
        ctime = os.path.getctime(file)         # 생성시간
        ctime = ctime_to_datetime(ctime).strftime('%Y-%m-%d %H:%M:%S') # 생성시간 datetime으로 변환

        #result = analysis(file, model)
        # 원본이미지 파일 경로도 저장
        original_filepath = dir_path + '/' + filename

        # result가 없다면, 해당 result를 None으로 변환
        if not result:
            result = None

        data = {
            'filename' : filename,
            'filepath' : filepath,
            'ctime' : ctime,
            'result' : result,
            'original_filepath' : original_filepath
        }

        json_file_path = os.path.splitext(filepath)[0]+ '.json'

        with open(json_file_path, 'w') as json_file:
            json.dump(data, json_file, indent=2)
    
        json_file_list.append(json_file_path)

    file_path = save_path + '/file_list.json'

    merge_json_files(json_file_list, file_path)

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
    with open(class_cnt_path, 'w') as json_file:
        json.dump(class_cnt, json_file, indent=2)

    print("\n객체 이름과 개수를 저장한 JSON 파일 생성 완료")

    end_time = time.time()

    print("\n걸린 시간 : ", end_time - start_time)