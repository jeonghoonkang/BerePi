# -*- coding:utf-8 -*-

'''
    Author : http://github.com/jeonghoonkang
'''

from __future__ import print_function
import argparse
import pandas as pd
import os
import sys
import math
import xlsxwriter


def brush_argparse():

    parser = argparse.ArgumentParser()
    #parser.add_argument("-xlsx", help="xlsx 파일 이름", action="store_true")
    parser.add_argument("-xlsx", help="xlsx 파일 이름")
    args = parser.parse_args()

    return args


if __name__ =='__main__':

    filename = 'car_ids.py'

    _args_pack_ = brush_argparse()
    #print (_args_pack_)
    _args_ = vars(_args_pack_)
    #print (_args_)  #key xlsx : value 파일명.확장명 
    _input_xlsx = _args_['xlsx'] 
    if _input_xlsx == None:
        print ('Please input xlsx filename on cli run argument')
        sys.exit(0)
        # 파일 리스트를 보여주고 선택하도록 기능 추가

    dframe = pd.read_excel(_input_xlsx, sheet_name='201906')
    dframe = dframe.sort_values(["COUNT"], ascending=[False]).reset_index(drop=True)
    carID = dframe["PHONE_NUM"].unique()
    id_list = carID.tolist()
    #print (type(id_list))

    # to String, save list object to string

    __ofile = open(filename,"w")
    __ofile.write(__odata)
    __ofile.close()

