import httplib
import time
conn = httplib.HTTPConnection("10.xxx.xxx.xxxx")

hue_uid = "c274b3c285d19cfxxxxxxxxxx"
restcmd = "/api"+hue_uid+"/lights"

str = " "
xhue = [10000,25000,46000,56280]

def shifthue() :
    global str
    global xhue
    xhue.insert(0,xhue[-1])
    xhue = xhue[0:4] 
    print xhue
    for num in range(0,4) :
        callurl = restcmd + "/%s/state"%(4-num)
        print callurl
        huenumber = (xhue[num])
        conn.request("PUT",callurl ,'{"on":true, "sat":254, "bri":254, "hue":%s}'%huenumber)
        response = conn.getresponse()
        data = response.read()
        print data
        
if __name__ == "__main__": 
#   print web()
    while True :
        shifthue()
        time.sleep(5
