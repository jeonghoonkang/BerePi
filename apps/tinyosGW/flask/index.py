import os
from flask import Flask
#import json
#import readfiles
app = Flask(__name__)

FILE_PATH = "./server"

def getFileList():
    return os.listdir(FILE_PATH)

def listToHref(fromList):
    res = ''
    for listItem in fromList:
        res += "<a href='./GW/%s'>%s</a><br />\n\r" % (listItem, listItem)
    return res

@app.route('/GW/<GWname>')
def getPublicIP(GWname):
    res = ''
    filepath = "%s/%s" % (FILE_PATH, GWname)
    f = open(filepath, "r")
    lines = f.readlines()
    return '<br />'.join(lines)

@app.route("/")
def index():
    files = getFileList()
    rs = '<br />'.join(files)
    rs = listToHref(files)
    return rs

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
