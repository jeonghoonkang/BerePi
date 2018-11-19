# -*- coding: utf-8 -*-
# Author : https://github.com/kmlee408
#          https://github.com/jeonghoonkang

'''
    부산 URL= http://openapi.airkorea.or.kr/openapi/services/rest/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty?serviceKey=fCRWi0DoCfoCPMHyDwai3trva10y4qb8mh9aysoHzvLKDWw6Q2bWOsvuM4%2BsRdvE4dPiKqBFD7vj7%2FM2noCe2g%3D%3D&ver=1.3&pageSize=10&pageNo=1&sidoName=%EB%B6%80%EC%82%B0&startPage=1&numOfRows=100

    실행 방법=  $python mdust_pusan.py
    (지역을 바꾸고 싶으면 misaemunji 함수 안에 location = '경기'  와 같은 식으로 변경)
    (측정 가능 지역: 서울, 부산, 대구, 인천, 광주, 대전, 울산, 경기, 강원, 충북, 충남, 전북, 전남, 경북, 경남, 제주, 세종)
    '''
    
import requests
from urllib import urlencode, quote_plus
from bs4 import BeautifulSoup
import pandas as pd
import keytxt

   # 서비스키는 data.go.kr 에서 받아야 함
   # https://www.data.go.kr/dataset/15000581/openapi.do?mypageFlag=Y

service_key = keytxt.key

def misaemunji(service_key, location=None, spot=None):

    #location으로 가능한 것: 서울, 부산, 대구, 인천, 광주, 대전, 울산, 경기, 강원, 충북, 충남, 전북, 전남, 경북, 경남, 제주, 세종
    
    #시도별 실시간 측정 조회 api
    URL ='http://openapi.airkorea.or.kr/openapi/services/rest/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty?serviceKey='

    # URL 인자 설정 및 인코딩
    queryParams = '&' + urlencode({quote_plus('numOfRows') : '100', # 최대로 설정
                                   quote_plus('pageSize'): '10',
                                   quote_plus('pageNo') : '1',
                                   quote_plus('startPage') :'1',
                                   quote_plus('sidoName') : location,
                                   quote_plus('ver') : '1.3'
                                   })

    if location == None : 
        exit ('you shoud write location such like 부산')

    r = requests.get(URL+service_key+queryParams)
    html = r.text
    soup = BeautifulSoup(html, 'html.parser') #parsing
    info_ = soup.select('item')

    misae_station = {}
    for info__ in info_:
        datetime_ = info__.datatime.text 
        list_ = [str(info__.pm10value.text),str(info__.pm25value.text)]
            # list 미세먼지 측정값 2가지
        misae_station[info__.stationname.text.encode('utf-8')] =list_
            # misae_station 은 기상대 이름별로 pm2.5, pm10 데이터를 담고 있음
    
    #dataframe 생성
    index_list = ['미세먼지10','초미세먼지2.5']
    df = pd.DataFrame(misae_station, index = index_list) 
    if spot != None :
        if spot in misae_station:
            '''
            print('측정시간 : ' + str(datetime_)), 2018-11-08 20:00
            print('측정지역 : ')
            print(location)
            print(spot) 
            print('(단위 : ㎍/㎥)')
            print misae_station[spot][1]
                '''
            return (str(datetime_), str(spot), 'pm2.5', misae_station[spot][1]  )
    
def get_public_mise(loc='서울', station='강남구'):
    
    kangnam = misaemunji(service_key, location=loc, spot=station) 
    return kangnam

if __name__ == '__main__':
    
    kangnam = misaemunji(service_key, location='서울', spot='강남구') 
    #location으로 가능한 것: 서울, 부산, 대구, 인천, 광주, 대전, 울산, 경기, 강원, 충북, 충남, 전북, 전남, 경북, 경남, 제주, 세종
    print kangnam


