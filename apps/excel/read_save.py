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

    
    
def diff_site_number(__class, target, inv_led):
    inv_led_sheets = inv_led.get_sheet_names()

    # 인버터 사업장 번호 추출
    inv_sheet = inv_led.get_sheet_by_name(inv_led_sheets[0])
    inv_company_nums = __class.read_vertical(inv_sheet, 'b4', 'b101')

    # LED 사업장 번호 추출
    led_sheet = inv_led.get_sheet_by_name(inv_led_sheets[1])
    led_company_nums = __class.read_vertical(led_sheet, 'b4', 'b416')

    # 통합파일 사업장 번호 추출
    target_sheets = target.get_sheet_names()
    target_sht1 = target.get_sheet_by_name(target_sheets[0])
    target_company_nums = __class.read_vertical(target_sht1, 'a3', 'a561')

    invs = list()
    leds = list()

    # 인버터 사업장 번호 비교
    ibn = len(inv_company_nums)
    tbn = len(target_company_nums)

    #diff count
    diff_cnt = 0

    # 유니코드로 변환
    inv = [unicode(i) for i in inv_company_nums]
    led = [unicode(i) for i in led_company_nums]
    target = [unicode(i) for i in target_company_nums]

    # 두개 파일에 존재하는 사업장 번호 검색
    # EA 파일에 있는 아이디가 EE 파일에 없는 경우 찾음
    # 리스트의 count 함수 이용. 일치하는 멤버없으면 0 리턴, 존재 갯수 리턴
    for idx in range(0, tbn):
        dtect_id = (target[idx])
        ix_inv = inv.count(dtect_id)
        ix_led = led.count(dtect_id)
        # 인버터, LED 리스트에 해당 사업장번호 없음
        if (ix_inv + ix_led) == 0 :
            diff_cnt = diff_cnt + 1
            invs.append([dtect_id, 'is_not_appered_in_NURI_file'])

    # 비교 결과 저장
    __t = datetime.datetime.now().strftime("%Y-%m-%d %H.%M.%S")
    wb = Workbook()
    ws = wb.active
    file_name = '_del_able_result_no_' + __t + '.xlsx'
    idx = 1

    for item in invs:
        #if item[2] is None : continue
        ws["A" + str(idx)] = item[0]
        ws["B" + str(idx)] = item[1]
        idx += 1

    wb.save(file_name)
    wb.close()

    

if __name__ == "__main__":

# open excell file
    eclass = excell_class()
    op = eclass.open_exc_doc()
    sheets = op.get_sheet_names()

    sh1 = op.get_sheet_by_name(sheets[0])
    buf = eclass.read_vertical(sh1,'b1','b541')

    save_vdata(err_buf)

    exit (" ...congrats, finish")
