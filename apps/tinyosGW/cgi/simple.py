#!/usr/bin/python
#-*- coding: UTF-8-*-

import cgi
import cgitb
import os
import sys

sys.path.append("/home/tinyos/devel/BerePi/apps/tinyosGW/cgi")
#import simple


if __name__ == "__main__":

    cgitb.enable()
    args = cgi.FieldStorage()  
    #print os.environ.items()

    print "Content-type: text/html\n"
    
    print "Simple CGI, Python ! <br>"
    print args


# sample
# http://10.0.2.4/cgi-bin/simple.py?Id=4&time=2017/01/01
# FieldStorage(None, None, [MiniFieldStorage('Id', '4'), MiniFieldStorage('time', '2017/01/01')])
