#!/usr/bin/python3

import os
import cgi

def printFile():
    pass

#경로를 설정하지 않으면 현재 파일 경로 사용
def printFilesList(path_dir=os.getcwd()+'/out/'):
    return os.listdir(path_dir)

form = cgi.FieldStorage()
if 'parameter' in form:
    fileContent = form['parameter'].value
    webContent = open('out/'+fileContent, 'r').read()
else:
    fileContent = None 
    webContent = None

print("Content-type:text/html\r\n\r\n")
print('<html>')
print('<head>')
print('<title>tinyosGW status</title>')
print('</head>')
print('<body>')
print('<h2>tinyosGW status</h2>')
print('<ol>')
for file_name in printFilesList():
    print('<li><a href="index.py?parameter='+file_name+'">'+file_name+'</a></li>')
print('</ol>')
print('<p>{webcontent}</p>'.format(webcontent=webContent))
print('</body>')
print('</html>')

#추가작성
#1.파일 확장자 제거
#2.파일명 확인 (*.log 파일만 읽기)
#3.파일 내용 출력시 엔터 추가
