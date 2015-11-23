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

    callurl = restcmd + "/4/state"
    
    try:
        conn.request("PUT",callurl ,'{"on":false}')
        response = conn.getresponse()
        data = response.read()
    except:
        print "keep goging...."
        time.sleep(2)

    time.sleep(1)
    for num in [3,2,1,4] :
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
        except:
            print "exception conn.getresponse from Hue GW"
            time.sleep(2)


        
if __name__ == "__main__": 
#   print web()
    while True :
        shifthue()
        time.sleep(5
