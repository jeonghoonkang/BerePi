#!/usr/bin/python3

import os
import cgi

#Check the .log file and return to just file name
def chkFileExt(filename):
    if filename.find('.log') > 0:
        filename = filename.split('.')[0]
    else:
        return None
    return str(filename)

#convert from escape sequence to html (/n > <br>, /r > <br>)
def fileToHTML(content):
    content = content.replace('\n', '<br>')
    content = content.replace('\r', '<br>')
    return content

#경로를 설정하지 않으면 현재 파일 경로 사용
def printFilesList(path_dir=os.getcwd()+'/out/'):
    return os.listdir(path_dir)

#start to cgi
form = cgi.FieldStorage()
if 'parameter' in form:
    fileContent = form['parameter'].value
    webContent = open('out/'+fileContent, 'r').read()
else:
    fileContent = None 
    webContent = ""

print("Content-type:text/html\r\n\r\n")
print('<html>')
print('<head>')
print('<title>tinyosGW status</title>')
print('</head>')
print('<body>')
print('<h2>tinyosGW status</h2>')
print('<ol>')
for file_name in printFilesList():
    if chkFileExt(file_name): print('<li><a href="index.py?parameter='+file_name+'">'+str(chkFileExt(file_name))+'</a></li>')
print('</ol>')
print('<p>{webcontent}</p>'.format(webcontent=fileToHTML(webContent)))
print('</body>')
print('</html>')
