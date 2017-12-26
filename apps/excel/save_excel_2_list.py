
# -*-coding:utf8-*-
# Author : Jeonghoon Kang, https://github.com/jeonghoonkang

from __future__ import print_function
from openpyxl.styles import PatternFill
from openpyxl import Workbook
import openpyxl
import argparse
import sys
import pickle

class excell_class :
    __ofile = None

    def __init__(self):
        pass

    #@staticmethod
    def open_exc_doc(self,__file):
        # using unicode file name with u syntax
        __ofile = openpyxl.load_workbook(__file)

        # pout = "ix: %s, mdsid: %s, donecheck: %d \r" %(ix, mds_id, donecheck)
        pout = "   ... file opened \n"
        sys.stdout.write(pout)
        sys.stdout.flush()
        return __ofile

    def read_vertical(self, sheet, __start, __end):
        __vertical = []
        # print " ... Please use column[n]:column[m], vertical read "
        cell_of_col = sheet[__start:__end]
        for row in cell_of_col:
            for cell in row:
                v = cell.value
                if v == None:
                    v ='None'
                __vertical.append(v)
        return __vertical  # __cnt, __cnt_n # 세로 셀 데이터, 데이터 갯수, None 갯수


def parse_args():
    story = u"파일명, 데이터 시작셀과 마지막셀 입력"
    usg = u'\n python save_list.py -f "sample" -t 0 -s T4 -e T38'
    parser = argparse.ArgumentParser(description=story, usage=usg, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-f", default="2017-07-24 17.12.00_new_ee_with_DB", help=u"파일명")
    parser.add_argument("-t", default="0", help=u"Sheet Tab: 0, 1, 2 ...")
    parser.add_argument("-s", default='G2', help=u"데이터 시작 셀")
    parser.add_argument("-e", default='G746', help=u"데이터 마지막 셀")
    args = parser.parse_args()

    # check
    f = args.f
    t = args.t
    s = args.s
    e = args.e
    return f, t, s, e

def check_color_list(__sheet, __list,__b_list,__start,__end, color):

    target_sheet = __sheet
    target_list = __list
    ## Exactly same


    color_list = []
    if color == "000000":
        rgbcolor = "00" + color
    else :
        rgbcolor = "FF" + color

    for idx in range(len(target_list)):
        if target_list[idx] == 'None':
            continue
        if (str(target_sheet[ __start[0] + str(idx+int(__start[1]))].fill.fgColor.rgb) == rgbcolor):
            color_list.append([target_list[idx].encode('utf-8'),__b_list[idx].encode('utf-8')])

    return color_list

def make_list(__targetlist,__list,__b_list, __things):

    target_list = __targetlist

    things_list = []

    for idx in range(len(target_list)):
        if target_list[idx] == 'None':
            continue
        if __list[idx] == __things:
            things_list.append([target_list[idx].encode('utf-8'),__b_list[idx].encode('utf-8')])

    return things_list


def save_list(__class, _file):
    # load an excel file
    _sheets = _file.get_sheet_names()
    _shname = _sheets[int(tab)]
    _sheet = _file.get_sheet_by_name(_shname)
    _out_list = __class.read_vertical(_sheet, start_range, end_range)
    #led_inv_list = __class.read_vertical(_sheet, 'F2', 'F746')
    #status_list = __class.read_vertical(_sheet, 'E2', 'E746')
    #business_list = __class.read_vertical(_sheet, 'A2', 'A746')

    #open a new file
    #f = open('_business_mds_id.py','w')

    #dump
    #pickle.dump(target_list, f)

    # write on file
    mds_id_list = []
    modem_list = []
    led_list = []
    inv_list = []
    good_list = []
    bad_list = []
    nuri_list = []
    db_list = []
    unique_list = []
    non_unique_list = []

    for idx in range(len(_out_list)):
        if _out_list[idx] == 'None':
            continue
        modem_list.append( [_out_list[idx].encode('utf-8')] )
    print ('len =', len(modem_list))

    _fn = './out_list.py'
    _listn = ''
    _ofile = open (_fn, 'a')
    print ("modem_list=", file = _ofile)
    print (modem_list, file = _ofile)

    _ofile.close()
    return 

if __name__ == "__main__":

    filename, tab, start_range, end_range = parse_args()
    cfile = excell_class()
    filename = cfile.open_exc_doc(filename + '.xlsx')

    save_list(cfile, filename)

