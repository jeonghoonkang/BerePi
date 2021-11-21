
# -*- coding: utf-8 -*-
#Author : https://github.com/jeonghoonkang

#import text as txt
import pandas as pd
import os
import sys 
import pickle
import info #read info for processing
import gc


def change_string_to_arry(fstring):
    sub_buf=[]
    _line_num = 0

    _firstlist = fstring.split(",")   
    print (_firstlist)
    _range_end = len(_firstlist)
    print ("length of list :", _range_end)

    return _firstlist


def df_rm_header(dfobj, lines=1):
    #csvobj remove header #lines of line
    return dfobj 


def recursive_search_dir(_nowDir, _filelist):
    print(" [r-loop] CSV recursive searching ", _nowDir)

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
        print("...done")


def csv_to_df_merge(_flist, fnum=None): #csv 파일을 하나의 dataframe 으로 변환 
    
    if fnum != None :
        _flist = _flist[:fnum] #fnum 갯수로 제한

    allData = []# 읽어 들인 csv파일 내용을 저장할 빈 리스트를 하나 만든다
    _dataframe = pd.DataFrame()
    cnt = 0
    print(" 디렉토리 모든 CSV를 데이터프레임으로 변환중 ...")
    for file in _flist:
        cnt += 1
        printProgressBar(cnt, len(_flist))
        _csvdf = pd.read_csv(file, skiprows = 3, header = None) 
        allData.append(_csvdf) # 리스트에 추가 
        #_dataframe.append(_csvdf)
        del [[_csvdf]]
        gc.collect()
    
    _dataframe = pd.concat(allData, axis=0, ignore_index=True)
    print (cnt, "개의 파일을 처리했습니다.. ")
    return _dataframe

def df_to_csv(_d, _h=None):

    if _h != None : 
        print ("CSV with Header ... ")
        _d.columns = _h
        _d.to_csv("_o_df_2_csv.csv", header=True, index=False) #인덱스 없이 저장
    else :
        print ("CSV without Header ... ")    
        _d.to_csv("_o_df_2_csv.csv", header=False, index=False) 


def _dataframe_print_(_d):
    print (_d.head(10))
    print (_d.sample(20))    
    print (_d.tail(10))


if __name__== "__main__" :

    print ("디렉토리 경로", info.local_path)

    file_list = []
    _d_limit_f_=1000 # 개발에만 사용 일부 파일만 테스트, 테스트 파일 갯수
    csvpath = info.local_path

    recursive_search_dir(csvpath, file_list)

    print (file_list[:10])    
    print (" ↑ 처리 대상 파일 중 10개")    
    print (len(file_list))

    df_m = csv_to_df_merge(file_list, _d_limit_f_)
    print ("Dataframe 라인갯수", len(df_m.index))
    _dataframe_print_(df_m)

    _header = info.fields_name
    header_list = change_string_to_arry(_header)

    df_to_csv(df_m, header_list)

    __f = open("_o_df.pkl","wb")
    pickle.dump(df_m,__f) 
    __f.close()



    # df_m = pd.read_csv(file_list[0], skiprows = 3, header = None) 
    # df = pd.read_pickle("df.pkl")
    # f = open("df.pkl", "rb")
    # temp = pickle.load(f)
    # f.close() 
    # df = pd.read_csv ('file_name.csv',usecols= ['column_name1','column_name2']) #subset of fields, sep='\t'
    # header=0, default, the first row of the CSV file will be treated as column names, header=None
    # df = pd.read_csv('example.csv', skiprows = 1,header = None)   

    # Ref.
    # https://towardsdatascience.com/how-to-read-csv-file-using-pandas-ab1f5e7e7b58
    # https://www.edureka.co/community/42836/how-to-read-pandas-csv-file-with-no-header

