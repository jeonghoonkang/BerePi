# -*- coding: utf-8 -*-
#Author : https://github.com/jeonghoonkang

import text as txt
import pandas as pd
import os
import sys 
import info #read info for processing

def change_string_to_arry(fstring):
    sub_buf=[]
    for idx in range(0,range_end) :
        line_num += 1
        print (line_num, firstlist[idx], "<##>", secondlist[idx])
        #sub_buf.append(line_num)
        sub_buf.append(firstlist[idx])
        sub_buf.append(secondlist[idx])
        buf.append(sub_buf)
        sub_buf=[]
    return field_list

def df_rm_header(dfobj, lines=1):
    #csvobj remove header #lines of line
    return dfobj 

def recursive_search_dir(_nowDir, _filelist):
    print(" [loop] recursive searching ", _nowDir)

    if os.path.isfile(_nowDir):
        file_extension = os.path.splitext(_nowDir)[1]
        if file_extension == ".csv" or file_extension == ".CSV":
            _filelist.append(_nowDir)
        return None

    dir_list = []  # 현재 디렉토리의 서브디렉토리가 담길 list
    f_list = os.listdir(_nowDir)
    for fname in f_list:
        file_extension = os.path.splitext(fname)[1]
        if os.path.isdir(_nowDir + "/" + fname):
            dir_list.append(_nowDir + "/" + fname)
        elif os.path.isfile(_nowDir + "/" + fname):
            if file_extension == ".csv" or file_extension == ".CSV":
                _filelist.append(_nowDir + "/" + fname)

    for toDir in dir_list:
        recursive_search_dir(toDir, _filelist)

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

def csv_to_df_total(_flist):
    allData = []# 읽어 들인 csv파일 내용을 저장할 빈 리스트를 하나 만든다
    cnt = 0
    print(" 디렉토리 모든 CSV를 데이터프레임으로 변환중 ...")
    for file in _flist:
        cnt += 1
        printProgressBar(cnt, len(_flist))
        df = pd.read_csv(file, skiprows = 2, header = None) # for구문으로 csv파일들을 읽어 들인다
        allData.append(df) # 빈 리스트에 읽어 들인 내용을 추가한다
    
    dataCombine = pd.concat(allData, axis=0, ignore_index=True)
    print (cnt, "개의 파일을 처리했습니다.. 아래는 샘플입니다 ")
    print ("라인스", len(dataCombine.index))
    dataCombine.sampel(30)
    return dataCombine

if __name__== "__main__" :
    print ("디렉토리 경로", info.local_path)
    file_list = []

    csvpath = info.local_path

    recursive_search_dir(csvpath, file_list)

    print (file_list)    
    print (len(file_list))
    #
    #csv_to_df_total(file_list)


    #df = pd.read_csv ('file_name.csv',usecols= ['column_name1','column_name2']) #subset of fields, sep='\t'
    #header=0, default, the first row of the CSV file will be treated as column names, header=None
    #df = pd.read_csv('example.csv', skiprows = 1,header = None)   



# Ref.
# https://towardsdatascience.com/how-to-read-csv-file-using-pandas-ab1f5e7e7b58
# https://www.edureka.co/community/42836/how-to-read-pandas-csv-file-with-no-header

