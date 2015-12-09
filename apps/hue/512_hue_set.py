# -*- coding: utf-8 -*-
import httplib
import time
from time import strftime, localtime


hue_uid = "c274b3c285d19cf3480c91439329147"
restcmd = "/api"+hue_uid+"/lights"

str = " "

latest_time = "initial status"
xhue = [10000,25000,46000,56280]
def shifthue() :
    global str
    global xhue
    global latest_time
    xhue.insert(0,xhue[-1])
    xhue = xhue[0:4] 
    print xhue

    conn = httplib.HTTPConnection("10.255.255.65")
    callurl = restcmd + "/4/state"
    """
    try:
        conn.request("PUT",callurl ,'{"on":false}')
        response = conn.getresponse()
        data = response.read()
    except:
        print "keep goging...."
        time.sleep(4)
    time.sleep(1)
    """
    for num in [4,3,2,1] :
        callurl = restcmd + "/%s/state"%(num)
        print callurl
        huenumber = (xhue[4-num])

        try :
            conn.request("PUT",callurl ,'{"on":false}')
            response = conn.getresponse()
            data = response.read()
            time.sleep(1)

            conn.request("PUT",callurl ,'{"on":true, "sat":254, "bri":254, "hue":%s}'%huenumber)
            response = conn.getresponse()
            data = response.read()
            print data
            time.sleep(1)
        
            latest_time = time_chk()

        except (httplib.HTTPException) as e :
            print latest_time, "HTTPException", e.args[0]
            time.sleep(4)
            conn = httplib.HTTPConnection("10.255.255.65")

        finally :
            time.sleep(0.3)
            conn = httplib.HTTPConnection("10.255.255.65")

def time_chk():
    time = strftime("%Y-%m%d %H:%M",localtime())
    return time

def hue4on():
	global str
	conn.request("PUT",restcmd+"/4/state", '{"on":true}')
	response = conn.getresponse()
	data = response.read()
	str = data + '<br>'
	time.sleep(2)
	return web()

def hue4off():
	global str
	conn.request("PUT",restcmd+"/4/state", '{"on":false}')
	response = conn.getresponse()
	data = response.read()
	str = data + '<br>'
	time.sleep(2)
	return web()

def hue3on():
	global str
	conn.request("PUT","/api/newdeveloper/lights/3/state", '{"on":true}')
	response = conn.getresponse()
	data = response.read()
	str = data + '<br>'
	time.sleep(2)
	return web()

def hue3off():
	global str
	conn.request("PUT","/api/newdeveloper/lights/3/state", '{"on":false}')
	response = conn.getresponse()
	data = response.read()
	str = data + '<br>'
	time.sleep(2)
	return web()


def hue5on():
	global str
	conn.request("PUT","/api/newdeveloper/lights/5/state", '{"on":true}')
	response = conn.getresponse()
	data = response.read()
	str = data + '<br>'
	time.sleep(2)
	return web()

def hue5off():
	global str
	conn.request("PUT","/api/newdeveloper/lights/5/state", '{"on":false}')
	response = conn.getresponse()
	data = response.read()
	str = data + '<br>'
	time.sleep(2)
	return web()

#########################################################################
## This is a sample controller
## - index is the default action of any application
## - user is required for authentication and authorization
## - download is for downloading files uploaded in the db (does streaming)
## - api is an example of Hypermedia API support and access control
#########################################################################

URL = 'http://iot.iptime.org:8000'

def web():
	global str
	str += '<img src="http://www2.meethue.com/media/957286/BAU-hue-Korea_threebytwo.jpg" width=800>'
	str += '<font size="40"> <br> <br> 거실 스탠드'
	str += ' <a href="http://iot.iptime.org:8000/thing/test/hue4off"> off </a>  또는'
	str += '<a href="http://iot.iptime.org:8000/thing/test/hue4on">  on </a> <br> <br>'
	str += ' 안방 스탠드'
	str += ' <a href="http://iot.iptime.org:8000/thing/test/hue3off"> off </a>  또는'
	str += '<a href="http://iot.iptime.org:8000/thing/test/hue3on">  on </a>'
	str += '<font size="40"> <br> <br> 숙소 스탠드'
	str += ' <a href="http://iot.iptime.org:8000/thing/test/hue5off"> off </a>  또는'
	str += '<a href="http://iot.iptime.org:8000/thing/test/hue5on">  on </a> <br> <br>'
	str += '</font> <br> <br> <br>'
   # str += '<img src=" http://125.7.128.53:4242/q?start=36h-ago&m=sum:gyu_RC1_co2.ppm%7Bnodeid=920%7d&o=&m=sum:gyu_RC1_thl.temperature%7Bnodeid=915%7d&o=axis%20x1y2&wxh=400x300&key=out%20bottom%20center&autoreload=15&png&.png" width=800> '
	rstr = str
	str = ''
	return rstr	


def index():
    """
    example action using the internationalization operator T and flash
    rendered by views/default/index.html or views/generic.html
    if you need a simple wiki simply replace the two lines below with:
    return auth.wiki()
    """
    response.flash = T("Welcome to web2py!")
    return dict(message=T('Hello World'))


def user():
    """
    exposes:
    http://..../[app]/default/user/login
    http://..../[app]/default/user/logout
    http://..../[app]/default/user/register
    http://..../[app]/default/user/profile
    http://..../[app]/default/user/retrieve_password
    http://..../[app]/default/user/change_password
    http://..../[app]/default/user/manage_users (requires membership in
    use @auth.requires_login()
        @auth.requires_membership('group name')
        @auth.requires_permission('read','table name',record_id)
    to decorate functions that need access control
    """
    return dict(form=auth())


#@cache.action()
def download():
    """
    allows downloading of uploaded files
    http://..../[app]/default/download/[filename]
    """
    return response.download(request, db)


def call():
    """
    exposes services. for example:
    http://..../[app]/default/call/jsonrpc
    decorate with @services.jsonrpc the functions to expose
    supports xml, json, xmlrpc, jsonrpc, amfrpc, rss, csv
    """
    return service()


#@auth.requires_login() 
def api():
    """
    this is example of API with access control
    WEB2PY provides Hypermedia API (Collection+JSON) Experimental
    """
    from gluon.contrib.hypermedia import Collection
    rules = {
        '<tablename>': {'GET':{},'POST':{},'PUT':{},'DELETE':{}},
        }
    return Collection(db).process(request,response,rules)




if __name__ == "__main__": 
#   print web()
    while True :
        shifthue()
        time.sleep(5)

