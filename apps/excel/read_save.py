# -*- coding: utf-8 -*-
# Author : jeonghoonkang , https://github.com/jeonghoonkang
# Author : jeongmoon417 , https://github.com/jeongmoon417

# 참고 url
# https://code.tutsplus.com/ko/tutorials/how-to-work-with-excel-documents-using-python--cms-25698
# http://egloos.zum.com/mcchae/v/11120944

import datetime

import openpyxl
import xlsxwriter
import sys
# sys.path.insert(0, '../doc_design')
# (to do) have to find how to add different location directory path and file
# now just using same dir location file

# from openpyxl.workbook import Workbook
# from openpyxl.writer.excel import ExcelWriter
# (error) from openpyxl.cell import get_column_letter
# from openpyxl import load_workbook

class excell_class :
    __ofile = None

    def __init__(self):
        pass

    #@staticmethod
    def open_exc_doc(self):
        # using unicode file name with u syntax
        __ofile = openpyxl.load_workbook(u"_test__1.xlsx")
        return __ofile

    def read_vertical(self, sheet, __start, __end):
        __vertical = []
        print " ... Please use column[n]:column[m], vertical read "
        cell_of_col = sheet[__start:__end]
        for row in cell_of_col:
            for cell in row:
                v = cell.value
                if v == None:
                    continue # do nothing below code, back to next for loop step
                __vertical.append(v) # 리스트 __vertical에 아이디 추가
        return __vertical #__cnt, __cnt_n # 세로 셀 데이터, 데이터 갯수, None 갯수


    # 입력 리스트를 액셀에 저장
    def save_exc (self, __vdata):
        __t = str(datetime.datetime.now())
        workbook = XlsxWriter.Workbook('takeout_id_result'+__t+'.xlsx')
        worksheet = workbook.add_worksheet()

        row = 0
        col = 0

        for item in (__vdata):
            worksheet.write(row, col, item)
            row += 1
        workbook.close()


def save_vdata(__vdata):
    __t = str(datetime.datetime.now())
    __odata = 'err_id_list='
    print str(__vdata)
    __odata = __odata + str(__vdata)
    print __odata

    filename = '__err_id_input_list_'+__t+'.py'
    __ofile = open(filename,"w")
    __ofile.write(__odata)
    __ofile.close()


if __name__ == "__main__":

# open excell file
    eclass = excell_class()
    op = eclass.open_exc_doc()
    sheets = op.get_sheet_names()

    sh1 = op.get_sheet_by_name(sheets[0])
    buf = eclass.read_vertical(sh1,'b1','b541')

    save_vdata(err_buf)

    exit (" ...congrats, finish")
