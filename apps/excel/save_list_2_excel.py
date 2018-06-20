# -*- coding: utf-8 -*-
# Author: Jeonghoon Kang, https://github.com/jeonghoonkang

import openpyxl
import argparse
import sys
#import pickle
import xlsxwriter


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
                    continue
                __vertical.append(v)
        return __vertical  # __cnt, __cnt_n # 세로 셀 데이터, 데이터 갯수, None 갯수

    def save_list_2_exl(self, _fn, _list1=None, _list2=None, _list3=None, _list4=None, _list5=None):
        workbook = xlsxwriter.Workbook(_fn+'.xlsx')
        worksheet = workbook.add_worksheet()
        if _list1 == None:
            print ("no list to save excel")
            return
        if _list1 != None:
            row = 0
            col = 1
            for item in (_list1):
                worksheet.write(row, col, item)
                row += 1
        if _list2 != None:
            row = 0
            col = 2
            for item in (_list2):
                worksheet.write(row, col, item)
                row += 1
        if _list3 != None:
            row = 0
            col = 3
            for item in (_list3):
                worksheet.write(row, col, item)
                row += 1
        if _list4 != None:
            row = 0
            col = 4
            for item in (_list4):
                worksheet.write(row, col, item)
                row += 1
        if _list5 != None:
            row = 0
            col = 5
            for item in (_list5):
                worksheet.write(row, col, item)
                row += 1
        workbook.close()




def parse_args():
    story = u"파일명, 데이터 시작셀과 마지막셀 입력"
    usg = u'\n python save_list.py -fname "sample" -s T4 -e T38'
    parser = argparse.ArgumentParser(description=story, usage=usg, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-f", default="sample", help=u"파일명, e.g.) sample")
    parser.add_argument("-s", default='T4', help=u"데이터 시작 셀, e.g.) T4")
    parser.add_argument("-e", default='T38', help=u"데이터 마지막 셀, e.g.) T38")
    parser.add_argument("-n", default='test.py', help=u"생성할 파일명, e.g) test.py")
    args = parser.parse_args()

    # check
    f = args.f
    s = args.s
    e = args.e
    n = args.n
    return f, s, e, n


if __name__ == "__main__":

    filename, start_range, end_range, new_name = parse_args()
    cfile = excell_class()
    _list = [0, 1, 2, 3, 4]
    cfile.save_list_2_exl('test_list_exl', _list)
